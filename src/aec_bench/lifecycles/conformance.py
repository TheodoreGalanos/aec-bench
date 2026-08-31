# ABOUTME: Provides reusable conformance checks for task-owned evidence lifecycles.
# ABOUTME: Runs real materializers, lifecycle reducers, recovery, visibility, and verifier paths.

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Any

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.harness.lifecycle_local import run_local_lifecycle
from aec_bench.lifecycles.application import LifecycleTrial, run_lifecycle_trial
from aec_bench.lifecycles.catalogue import verify_lifecycle
from aec_bench.lifecycles.compiled import compile_lifecycle
from aec_bench.lifecycles.runtime.definition import LifecycleDefinition
from aec_bench.lifecycles.runtime.episode import (
    InProcessLifecycleEpisodeEnvironment,
    LifecycleEpisodeContext,
    LifecycleEpisodeEnvironment,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleEpisodeUsage,
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.lifecycles.runtime.lifecycle import (
    EvidenceLifecycleError,
    branch_lifecycle,
    read_lifecycle,
    release_checkpoint,
    run_lifecycle,
    submit_checkpoint,
    validate_evidence_checkpoint_submission,
    validate_lifecycle_verification,
)
from aec_bench.trials import PlannedTrial

type LifecycleSubmissionWriter = Callable[[Path, Path, str, str, Path], None]

REQUIRED_GUARANTEES = frozenset(
    {
        "identity_and_variant_versions",
        "checkpoint_order_and_dependencies",
        "release_visibility",
        "submission_validation",
        "deterministic_transitions",
        "allowed_branch_origin",
        "recovery_without_repeated_effects",
        "hidden_verifier_exclusion",
        "completed_state_rejection",
        "normal_trial_record_mapping",
        "fresh_and_persistent_memory_contracts",
        "exact_id_and_version_resolution",
    }
)


@dataclass(frozen=True, slots=True)
class LifecycleConformanceCase:
    """One owner-local lifecycle conformance entry point."""

    template_id: str
    definition: LifecycleDefinition
    write_submission: LifecycleSubmissionWriter

    def __post_init__(self) -> None:
        if self.template_id != self.definition.metadata.template_id:
            raise ValueError("lifecycle conformance case does not match its definition")
        if not callable(self.write_submission):
            raise TypeError("lifecycle conformance submission writer must be callable")


class _RecordingEnvironment:
    """Record real host requests while preserving the owner environment behavior."""

    def __init__(
        self,
        wrapped: LifecycleEpisodeEnvironment,
        captured: list[LifecycleEpisodeRequest],
        *,
        execution_mode: LifecycleExecutionMode,
        visibility_policy: LifecycleVisibilityPolicy,
    ) -> None:
        self._wrapped = wrapped
        self.captured = captured
        self.execution_mode = execution_mode
        self.memory_visibility_policy = visibility_policy

    @property
    def requested_adapter(self) -> str:
        return self._wrapped.requested_adapter

    @property
    def requested_model(self) -> str:
        return self._wrapped.requested_model

    @property
    def max_turns_per_session(self) -> int:
        return self._wrapped.max_turns_per_session

    def recover(self, context: LifecycleEpisodeContext) -> None:
        self._wrapped.recover(context)

    def prepare(self, request: LifecycleEpisodeRequest) -> None:
        self._wrapped.prepare(request)

    def record_failure(
        self,
        request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        self._wrapped.record_failure(request, failure_kind=failure_kind, provider_error=provider_error)

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        self.captured.append(request)
        return self._wrapped.execute(request)


def build_lifecycle_conformance_case(definition: LifecycleDefinition) -> LifecycleConformanceCase:
    """Build the shared case for one concrete lifecycle owner."""

    return LifecycleConformanceCase(
        template_id=definition.metadata.template_id,
        definition=definition,
        write_submission=_write_gold_submission,
    )


def build_lifecycle_conformance_case_with_writer(
    definition: LifecycleDefinition,
    write_submission: LifecycleSubmissionWriter,
) -> LifecycleConformanceCase:
    """Build the shared case with one owner-local deterministic submission writer."""

    return LifecycleConformanceCase(
        template_id=definition.metadata.template_id,
        definition=definition,
        write_submission=write_submission,
    )


def _gold_environment(
    package_dir: Path,
    *,
    captured: list[LifecycleEpisodeRequest],
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT,
    visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
) -> InProcessLifecycleEpisodeEnvironment:
    submissions = json.loads((package_dir / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))

    def execute(request: LifecycleEpisodeRequest) -> dict[str, str]:
        captured.append(request)
        checkpoint_id = request.checkpoint_id
        submission_path = Path(request.submission_path)
        submission_path.parent.mkdir(parents=True, exist_ok=True)
        submission_path.write_text(json.dumps(submissions[checkpoint_id], sort_keys=True) + "\n", encoding="utf-8")
        return {"status": "completed"}

    def run(request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        execute(request)
        return LifecycleEpisodeResult(
            episode_id=request.episode_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            checkpoint_ids=request.checkpoint_ids,
            execution_mode=request.execution_mode,
            memory_visibility_policy=request.memory_visibility_policy,
            status="completed",
            requested_adapter="deterministic",
            requested_model="gold",
            max_turns_per_session=request.max_turns_per_session,
            adapter="in_process",
            resolved_model="gold",
            usage=LifecycleEpisodeUsage(),
        )

    return InProcessLifecycleEpisodeEnvironment(
        executor=run,
        execution_mode=execution_mode,
        memory_visibility_policy=visibility_policy,
    )


def _materialize(definition: LifecycleDefinition, root: Path) -> Path:
    return Path(definition.materializer(root))


def assert_lifecycle_conformance(
    definition: LifecycleDefinition,
    *,
    write_submission: LifecycleSubmissionWriter,
    seed: int = 0,
) -> None:
    """Execute all lifecycle guarantees for one owner definition."""

    identity = definition.identity
    assert identity.version > 0
    assert all(member.version > 0 for member in definition.variant_identities)
    assert definition.variant_ids is not None or not definition.variant_identities
    if definition.variant_ids is not None:
        assert tuple(sorted(definition.variant_ids())) == tuple(
            member.registration_id for member in definition.variant_identities
        )

    checkpoints = definition.lifecycle.checkpoints
    checkpoint_ids = tuple(item.checkpoint_id for item in checkpoints)
    assert len(checkpoint_ids) == len(set(checkpoint_ids))
    known: set[str] = set()
    for checkpoint in checkpoints:
        assert set(checkpoint.depends_on) <= known
        known.add(checkpoint.checkpoint_id)

    with TemporaryDirectory(prefix=f"aec-bench-lifecycle-conformance-{seed}-") as root:
        first_root = Path(root) / "first"
        second_root = Path(root) / "second"
        first_package = _materialize(definition, first_root / "package")
        second_package = _materialize(definition, second_root / "package")
        first_run = first_root / "run"
        second_run = second_root / "run"
        first_requests: list[LifecycleEpisodeRequest] = []
        second_requests: list[LifecycleEpisodeRequest] = []

        first_base_environment = definition.smoke_environment(first_package) if definition.smoke_environment else None
        second_base_environment = definition.smoke_environment(second_package) if definition.smoke_environment else None
        if first_base_environment is None:
            first_base_environment = _gold_environment(first_package, captured=[])
        if second_base_environment is None:
            second_base_environment = _gold_environment(second_package, captured=[])
        first_environment = _RecordingEnvironment(
            first_base_environment,
            first_requests,
            execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
            visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        )
        second_environment = _RecordingEnvironment(
            second_base_environment,
            second_requests,
            execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
            visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        )
        first_resolver = (
            definition.operation_resolver(first_package, first_run) if definition.operation_resolver else None
        )
        second_resolver = (
            definition.operation_resolver(second_package, second_run) if definition.operation_resolver else None
        )

        first_result = run_lifecycle(
            first_package,
            first_run,
            episode_environment=first_environment,
            operation_resolver=first_resolver,
        )
        second_result = run_lifecycle(
            second_package,
            second_run,
            episode_environment=second_environment,
            operation_resolver=second_resolver,
        )
        first_state = read_lifecycle(first_package, first_run, operation_resolver=first_resolver)
        second_state = read_lifecycle(second_package, second_run, operation_resolver=second_resolver)
        first_verification = validate_lifecycle_verification(definition.verifier(first_package, first_run))
        second_verification = validate_lifecycle_verification(definition.verifier(second_package, second_run))

        assert first_result["status"] == second_result["status"] == "complete"
        assert _comparable_state(first_state) == _comparable_state(second_state)
        assert first_verification == second_verification

        assert first_requests
        assert all(request.execution_mode is LifecycleExecutionMode.FRESH_CONTEXT for request in first_requests)
        assert all(
            request.memory_visibility_policy is LifecycleVisibilityPolicy.ARTIFACT_MEMORY for request in first_requests
        )

        for checkpoint in checkpoints:
            submission = json.loads(
                (first_run / "episodes" / checkpoint.checkpoint_id / "submission.json").read_text(encoding="utf-8")
            )
            validate_evidence_checkpoint_submission(checkpoint, submission)
        assert all("hidden" not in path for request in first_requests for path in request.released_files)
        assert all(
            "hidden" not in str(path)
            for checkpoint in first_state["checkpoint_runs"]
            for path in checkpoint.get("released_files", [])
        )

        before_repeat = len(first_requests)
        run_lifecycle(
            first_package,
            first_run,
            episode_environment=first_environment,
            operation_resolver=first_resolver,
        )
        assert len(first_requests) == before_repeat

        production_trial = _production_trial(definition, first_root / "production")
        production_record = run_lifecycle_trial(
            trial=production_trial,
            execute=lambda trial: run_local_lifecycle(
                trial=trial,
                adapter_builder=_OwnerAdapterBuilder(definition, trial.package_dir, trial.run_dir),
            ),
            verify=verify_lifecycle,
        )
        assert production_record.lifecycle_execution is not None
        assert production_record.lifecycle_execution.status == "completed"
        assert production_record.lifecycle_execution.execution_mode == "fresh_context"
        assert production_record.lifecycle_execution.memory_visibility_policy == "artifact_memory"
        assert production_record.evaluation is not None
        assert production_record.evaluation.validity.verifier_completed

        persistent_trial = _production_trial(
            definition,
            first_root / "persistent",
            execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
        )
        persistent_record = run_lifecycle_trial(
            trial=persistent_trial,
            execute=lambda trial: run_local_lifecycle(
                trial=trial,
                adapter_builder=_PersistentOwnerAdapterBuilder(definition, trial, write_submission),
            ),
            verify=verify_lifecycle,
        )
        assert persistent_record.lifecycle_execution is not None
        assert persistent_record.lifecycle_execution.status == "completed"
        assert persistent_record.lifecycle_execution.execution_mode == "persistent_context"
        assert persistent_record.lifecycle_execution.memory_visibility_policy == "persistent_context"
        assert len(persistent_record.lifecycle_execution.sessions) == 1

        first_checkpoint = checkpoint_ids[0]
        branch_run = first_root / "branch"
        branch_lifecycle(
            first_package,
            first_run,
            branch_run,
            operation_resolver=first_resolver,
            checkpoint_id=first_checkpoint,
            branch_id=f"conformance-{seed}-branch",
            reason="Conformance branch from a submitted checkpoint.",
        )
        branch_resolver = (
            definition.operation_resolver(first_package, branch_run) if definition.operation_resolver else None
        )
        branch_state = read_lifecycle(first_package, branch_run, operation_resolver=branch_resolver)
        assert branch_state["active_checkpoint_id"] == first_checkpoint
        assert branch_state["branch"]["branched_from_checkpoint_id"] == first_checkpoint
        if len(checkpoint_ids) > 1:
            with TemporaryDirectory(prefix=f"aec-bench-lifecycle-conformance-{seed}-invalid-branch-") as invalid_root:
                invalid_parent = Path(invalid_root) / "parent"
                invalid_parent_resolver = (
                    definition.operation_resolver(first_package, invalid_parent)
                    if definition.operation_resolver
                    else None
                )
                release_checkpoint(first_package, invalid_parent, operation_resolver=invalid_parent_resolver)
                try:
                    branch_lifecycle(
                        first_package,
                        invalid_parent,
                        Path(invalid_root) / "branch",
                        operation_resolver=invalid_parent_resolver,
                        checkpoint_id=checkpoint_ids[-1],
                        branch_id=f"invalid-{seed}",
                        reason="Attempt an origin that is not an allowed submitted checkpoint.",
                    )
                except EvidenceLifecycleError:
                    pass
                else:
                    raise AssertionError("lifecycle accepted a branch from an unavailable checkpoint")

        completed_state_before = read_lifecycle(first_package, first_run, operation_resolver=first_resolver)
        try:
            submit_checkpoint(first_package, first_run, operation_resolver=first_resolver, episode_result={})
        except EvidenceLifecycleError as exc:
            assert str(exc) == "no checkpoint is awaiting submission"
        else:
            raise AssertionError("completed lifecycle accepted a checkpoint submission")
        assert read_lifecycle(first_package, first_run, operation_resolver=first_resolver) == completed_state_before

        from aec_bench.lifecycles.catalogue import lifecycle_definition_by_identity

        assert lifecycle_definition_by_identity(identity.id, version=identity.version) is definition
        assert lifecycle_definition_by_identity(str(identity.key), version=identity.version) is definition

    assert first_verification["lifecycle_id"] == definition.lifecycle.lifecycle_id


def _comparable_state(state: dict[str, Any]) -> dict[str, Any]:
    """Remove only run-local paths and request hashes from deterministic state comparison."""

    return {
        key: value for key, value in state.items() if key not in {"workspace", "run_dir"} and key != "checkpoint_runs"
    } | {
        "checkpoint_runs": [
            {key: value for key, value in checkpoint.items() if key != "attempts"}
            | {
                "attempts": [
                    {key: value for key, value in attempt.items() if key != "episode_request_sha256"}
                    for attempt in checkpoint.get("attempts", [])
                ]
            }
            for checkpoint in state.get("checkpoint_runs", [])
        ]
    }


def _production_trial(
    definition: LifecycleDefinition,
    root: Path,
    *,
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT,
) -> LifecycleTrial:
    """Build one ordinary lifecycle trial for the production finalization path."""

    compiled = compile_lifecycle(definition.metadata.template_id, root / "package")
    return LifecycleTrial(
        planned=PlannedTrial(
            trial_id=f"conformance-{definition.metadata.template_id}",
            experiment_id="lifecycle-conformance",
            task_id=definition.metadata.template_id,
            agent=AgentConfig(
                name="conformance-agent",
                adapter="tool_loop",
                model="conformance-model",
                parameters={"max_turns_per_session": 20},
            ),
            compute=ComputeConfig(backend="local"),
            repetition=1,
        ),
        compiled=compiled,
        run_dir=root / "run",
        execution_mode=execution_mode,
        visibility_policy=(
            LifecycleVisibilityPolicy.PERSISTENT_CONTEXT
            if execution_mode is LifecycleExecutionMode.PERSISTENT_CONTEXT
            else LifecycleVisibilityPolicy.ARTIFACT_MEMORY
        ),
    )


def _write_gold_submission(package: Path, _run: Path, checkpoint_id: str, _session_id: str, output: Path) -> None:
    submissions = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(submissions[checkpoint_id]), encoding="utf-8")


class _PersistentOwnerAdapterBuilder:
    """Drive the normal persistent-session tools with an owner-local submission writer."""

    def __init__(
        self,
        definition: LifecycleDefinition,
        trial: LifecycleTrial,
        write_submission: LifecycleSubmissionWriter,
    ) -> None:
        self._definition = definition
        self._trial = trial
        self._write_submission = write_submission

    def __call__(self, **kwargs: Any) -> Any:
        submit = next(tool for tool in kwargs["native_tools"] if tool.__name__ == "submit_checkpoint")
        builder = self

        class _Adapter:
            def execute(self, _request: Any) -> Any:
                resolver = (
                    builder._definition.operation_resolver(builder._trial.package_dir, builder._trial.run_dir)
                    if builder._definition.operation_resolver
                    else None
                )
                while True:
                    state = read_lifecycle(
                        builder._trial.package_dir,
                        builder._trial.run_dir,
                        operation_resolver=resolver,
                    )
                    checkpoint_id = state["active_checkpoint_id"]
                    if checkpoint_id is None:
                        break
                    checkpoint_run = next(
                        item for item in state["checkpoint_runs"] if item["checkpoint_id"] == checkpoint_id
                    )
                    session_id = checkpoint_run["attempts"][-1]["session_id"]
                    context = release_checkpoint(
                        builder._trial.package_dir,
                        builder._trial.run_dir,
                        operation_resolver=resolver,
                    )
                    builder._write_submission(
                        builder._trial.package_dir,
                        builder._trial.run_dir,
                        checkpoint_id,
                        session_id,
                        Path(context["submission_path"]),
                    )
                    response = json.loads(submit(checkpoint_id))
                    if response["status"] == "complete":
                        break
                return _successful_adapter_result()

        return _Adapter()


def _successful_adapter_result() -> Any:
    return SimpleNamespace(
        adapter_name="tool_loop",
        resolved_model="conformance-model",
        configuration_record={"model": "conformance-model", "max_turns": 20},
        agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
        transcript=[],
        raw_output_text=None,
        provider_error=None,
        failure_kind=None,
        usage_input_tokens=2,
        usage_output_tokens=1,
        usage_cache_read_tokens=0,
        usage_cache_write_tokens=0,
    )


class _OwnerAdapterBuilder:
    """Adapt each owner's deterministic smoke executor to the normal local trial path."""

    def __init__(self, definition: LifecycleDefinition, package_dir: Path, run_dir: Path) -> None:
        self._package_dir = package_dir
        self._run_dir = run_dir
        self._smoke_environment = definition.smoke_environment(package_dir) if definition.smoke_environment else None
        gold_path = package_dir / "hidden" / "gold-submissions.json"
        self._submissions = json.loads(gold_path.read_text(encoding="utf-8")) if gold_path.is_file() else None

    def __call__(self, **_kwargs: Any) -> Any:
        submissions = self._submissions

        class _Adapter:
            def execute(self, request: Any) -> Any:
                output = Path(request.output_path)
                if submissions is not None:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(json.dumps(submissions[output.stem]), encoding="utf-8")
                else:
                    if builder._smoke_environment is None:
                        raise ValueError("lifecycle conformance requires a gold or smoke submission executor")
                    request_paths = sorted((builder._run_dir / "episodes" / output.stem).glob("*/episode_request.json"))
                    if not request_paths:
                        raise ValueError(f"lifecycle episode request is missing for {output.stem}")
                    lifecycle_request = LifecycleEpisodeRequest.model_validate_json(
                        request_paths[-1].read_text(encoding="utf-8")
                    )
                    result = builder._smoke_environment.execute(lifecycle_request)
                    if result.status != "completed":
                        raise ValueError(f"lifecycle smoke executor failed for {output.stem}")
                return _successful_adapter_result()

        builder = self
        return _Adapter()


def run_lifecycle_conformance(case: LifecycleConformanceCase, *, seed: int = 0) -> dict[str, Any]:
    """Run one owner case and return the twelve executed guarantee names."""

    assert_lifecycle_conformance(case.definition, write_submission=case.write_submission, seed=seed)
    return {"template_id": case.template_id, "proven": sorted(REQUIRED_GUARANTEES)}


def lifecycle_conformance_case(template_id: str) -> LifecycleConformanceCase:
    """Resolve one lifecycle case from generated owner descriptors."""

    from aec_bench.lifecycles.generated_catalogue import LIFECYCLE_DESCRIPTORS

    loaded_cases = tuple(descriptor.load_conformance_case() for descriptor in LIFECYCLE_DESCRIPTORS)
    for loaded in loaded_cases:
        if not isinstance(loaded, LifecycleConformanceCase):
            raise TypeError("lifecycle conformance entry point must return LifecycleConformanceCase")
        if loaded.template_id == template_id:
            return loaded
    known = ", ".join(sorted(case.template_id for case in loaded_cases if isinstance(case, LifecycleConformanceCase)))
    raise KeyError(f"unknown lifecycle conformance key: {template_id}. Known: {known}")


__all__ = (
    "LifecycleConformanceCase",
    "REQUIRED_GUARANTEES",
    "assert_lifecycle_conformance",
    "build_lifecycle_conformance_case",
    "build_lifecycle_conformance_case_with_writer",
    "lifecycle_conformance_case",
    "run_lifecycle_conformance",
)
