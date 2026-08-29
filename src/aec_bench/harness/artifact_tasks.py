# ABOUTME: Runs ordinary artifact-task attempts in isolated local workspaces.
# ABOUTME: Keeps one adapter execution separate from selection, verification, and persistence.

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, Field, PositiveInt

from aec_bench.adapters.base import Adapter, AdapterRequest, AdapterResult
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.canonical_refs import CanonicalRefSet, parse_canonical_refs
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.trial_extensions import ArtifactReference, VerifierExecutionReceipt
from aec_bench.contracts.trial_record import (
    EvaluationStatus,
    ExecutionStatus,
    TrialRecord,
)
from aec_bench.contracts.validators import StrictModel
from aec_bench.evaluation.normalisation import NormalisationResult, normalise_output
from aec_bench.evaluation.verifier_outcome import map_verifier_execution
from aec_bench.harness.local_runtime import (
    patch_workspace_paths,
    read_instruction,
    setup_workspace,
    stage_verifier_assets,
)
from aec_bench.harness.model_execution.llm_reviewer import ReviewerRunConfig, run_workspace_reviewer
from aec_bench.harness.trial_record_builder import build_trial_record
from aec_bench.harness.verifier_execution import (
    VERIFIER_PROTOCOL_VERSION,
    execute_verifier,
    localise_staged_verifier_paths,
)
from aec_bench.ledger.writer import materialize_trial_record
from aec_bench.tasks.instance import ResolvedTaskInstance
from aec_bench.tasks.snapshot import build_task_snapshot_archive
from aec_bench.trajectory.writer import TrajectoryWriter
from aec_bench.trials import PlannedTrial

AdapterBuilder = Callable[..., Adapter]
_VERIFIER_RETRY_PROMPT = "verifier_retry_prompt.md"
_VERIFIER_RETRY_TARGET_REWARD = 1.0
_VERIFIER_RETRY_ARTIFACT_SUFFIXES = (
    "_record.json",
    "_decision.json",
    "_readback_check.json",
    "_notice.json",
    "_report.json",
    "_marker.json",
)
_VERIFIER_RETRY_EXCLUDED_PREFIXES = ("expected_", "input_", "prior_", "source_")


class AttemptRunner(Protocol):
    def __call__(
        self,
        *,
        attempt_id: str,
        parent: TaskAttempt | None = None,
        instruction: str | None = None,
    ) -> TaskAttempt: ...


class AttemptRecipe(Protocol):
    def __call__(self, run_once: AttemptRunner) -> AttemptSelection: ...


class ImportedExperimentRuntime(Protocol):
    def run_experiment(
        self,
        *,
        tasks: Sequence[ResolvedTaskInstance],
        trials: Sequence[PlannedTrial],
        recipe_spec: AttemptRecipeSpec,
        reviewer: ReviewerRunConfig | None,
        verify: bool,
    ) -> list[TrialRecord]: ...


class AttemptSelector(Protocol):
    def __call__(self, candidates: Sequence[SelectorCandidate]) -> SelectorDecision: ...


@dataclass(frozen=True)
class SelectorCandidate:
    index: int
    attempt_id: str
    status: AgentOutputStatus
    primary_output: bytes | None
    output_reference: ArtifactReference | None

    @property
    def eligible(self) -> bool:
        return self.status is AgentOutputStatus.COMPLETED and bool(self.primary_output)


@dataclass(frozen=True)
class SelectorDecision:
    selected_index: int | None
    reason: str
    configuration: Mapping[str, object]
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class CandidateAttemptEvidence(StrictModel):
    index: int
    attempt_id: str
    status: AgentOutputStatus
    elapsed_seconds: float
    eligible: bool
    selector_visible_output: ArtifactReference | None = None


class SelectorEvidence(StrictModel):
    kind: Literal["self"] = "self"
    configuration: dict[str, object]
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    selected_index: int | None = None


class AttemptSelectionEvidence(StrictModel):
    candidates: tuple[CandidateAttemptEvidence, ...]
    selector: SelectorEvidence
    decision: Literal["selected", "failed"]
    reason: str
    selected_index: int | None = None


class SelfSelectorSpec(StrictModel):
    kind: Literal["self"] = "self"


class SingleAttemptSpec(StrictModel):
    kind: Literal["single_attempt"] = "single_attempt"


class BestOfSpec(StrictModel):
    kind: Literal["best_of"] = "best_of"
    candidates: PositiveInt
    selector: SelfSelectorSpec = Field(default_factory=SelfSelectorSpec)


AttemptRecipeSpec = Annotated[SingleAttemptSpec | BestOfSpec, Field(discriminator="kind")]


@dataclass(frozen=True)
class TaskAttempt:
    attempt_id: str
    trial_id: str
    parent_attempt_id: str | None
    workspace: Path
    request: AdapterRequest
    result: AdapterResult
    elapsed_seconds: float

    @property
    def status(self) -> AgentOutputStatus:
        return self.result.agent_output.status


@dataclass(frozen=True)
class AttemptSelection:
    attempt: TaskAttempt | None
    decision: str
    reason: str
    evidence: AttemptSelectionEvidence | None = None

    @classmethod
    def selected(
        cls,
        attempt: TaskAttempt,
        *,
        reason: str,
        evidence: AttemptSelectionEvidence | None = None,
    ) -> AttemptSelection:
        return cls(attempt=attempt, decision="selected", reason=reason, evidence=evidence)

    @classmethod
    def failed(
        cls,
        *,
        reason: str,
        evidence: AttemptSelectionEvidence | None = None,
    ) -> AttemptSelection:
        return cls(attempt=None, decision="failed", reason=reason, evidence=evidence)


class LocalTaskRuntime:
    """Execute exactly one local adapter call in an isolated workspace."""

    def __init__(
        self,
        *,
        work_root: Path | None = None,
        artifact_root: Path | None = None,
        adapter_builder: AdapterBuilder | None = None,
        constitutional_model: str | None = None,
        normalise: bool = True,
        agent_files: Mapping[str, Path] | None = None,
    ) -> None:
        self._work_root = work_root
        self._adapter_builder = adapter_builder
        self._constitutional_model = constitutional_model
        self._normalise = normalise
        self._agent_files = dict(agent_files or {})
        self._artifact_root = artifact_root or (
            (work_root / "artifacts")
            if work_root is not None
            else Path(tempfile.mkdtemp(prefix="aec-bench-artifacts-"))
        )
        self._artifact_root.parent.mkdir(parents=True, exist_ok=True)
        self._attempt_workspaces: list[Path] = []
        self._task_revisions: dict[Path, str] = {}

    @property
    def artifact_root(self) -> Path:
        return self._artifact_root

    @property
    def attempt_workspaces(self) -> tuple[Path, ...]:
        return tuple(self._attempt_workspaces)

    def task_revision(self, task: ResolvedTaskInstance) -> str:
        """Resolve one task revision once for all trials that use this runtime."""
        source = task.instance_dir.resolve()
        revision = self._task_revisions.get(source)
        if revision is None:
            revision = hashlib.sha256(build_task_snapshot_archive(source)).hexdigest()
            self._task_revisions[source] = revision
        return revision

    def run_once(
        self,
        task: ResolvedTaskInstance,
        trial: PlannedTrial,
        *,
        attempt_id: str,
        parent: TaskAttempt | None = None,
        instruction: str | None = None,
    ) -> TaskAttempt:
        if trial.task_id != task.task.task_id:
            raise ValueError("planned trial task_id does not match the resolved task")
        if parent is not None and parent.trial_id != trial.trial_id:
            raise ValueError("parent attempt belongs to another trial")

        workspace = self._create_workspace(task=task, parent=parent)
        self._attempt_workspaces.append(workspace)
        return self._execute_in_workspace(
            task=task,
            trial=trial,
            workspace=workspace,
            attempt_id=attempt_id,
            parent_attempt_id=None if parent is None else parent.attempt_id,
            instruction=instruction,
        )

    def _run_again(
        self,
        task: ResolvedTaskInstance,
        trial: PlannedTrial,
        *,
        attempt_id: str,
        parent: TaskAttempt,
        instruction: str,
    ) -> TaskAttempt:
        """Run one explicit reward-aware continuation in the parent's isolated workspace."""
        if parent.trial_id != trial.trial_id:
            raise ValueError("parent attempt belongs to another trial")
        return self._execute_in_workspace(
            task=task,
            trial=trial,
            workspace=parent.workspace,
            attempt_id=attempt_id,
            parent_attempt_id=parent.attempt_id,
            instruction=instruction,
        )

    def _execute_in_workspace(
        self,
        *,
        task: ResolvedTaskInstance,
        trial: PlannedTrial,
        workspace: Path,
        attempt_id: str,
        parent_attempt_id: str | None,
        instruction: str | None,
    ) -> TaskAttempt:
        request = self._build_request(task=task, trial=trial, workspace=workspace, instruction=instruction)
        adapter = self._build_adapter(trial=trial, workspace=workspace)
        started = time.monotonic()
        result = adapter.execute(request)
        elapsed_seconds = time.monotonic() - started

        output_path = resolve_workspace_path(workspace, task.task.verifier.expected_output_path)
        output_source = "adapter"
        if output_path.is_file() and output_path.read_text(encoding="utf-8", errors="replace").strip():
            output_source = "direct_write"
        elif result.raw_output_text:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.raw_output_text, encoding="utf-8")
            output_source = "raw_output"

        if self._normalise and output_path.is_file():
            refs = load_canonical_refs(task.instance_dir / "task.toml")
            if refs.refs:
                apply_normalisation(
                    output_path,
                    refs,
                    workspace / "normalisation_report.json",
                    committed_result=result,
                )
        validate_output_commit(
            result=result, output_path=output_path, expected_output_path=task.task.verifier.expected_output_path
        )
        _write_agent_result(
            workspace=workspace,
            requested_model=trial.agent.model,
            adapter_kind=trial.agent.adapter,
            result=result,
            output_source=output_source,
        )
        return TaskAttempt(
            attempt_id=attempt_id,
            trial_id=trial.trial_id,
            parent_attempt_id=parent_attempt_id,
            workspace=workspace,
            request=request,
            result=result,
            elapsed_seconds=elapsed_seconds,
        )

    def _create_workspace(self, *, task: ResolvedTaskInstance, parent: TaskAttempt | None) -> Path:
        if self._work_root is not None:
            self._work_root.mkdir(parents=True, exist_ok=True)
        if parent is None:
            workspace = Path(setup_workspace(str(task.instance_dir), work_root=self._work_root))
            self._copy_agent_files(workspace)
            patch_workspace_paths(str(workspace))
            return workspace

        workspace = Path(tempfile.mkdtemp(prefix="aec-bench-local-", dir=self._work_root))
        shutil.copytree(parent.workspace, workspace, dirs_exist_ok=True)
        shutil.rmtree(workspace / "tests", ignore_errors=True)
        shutil.rmtree(workspace / "logs" / "verifier", ignore_errors=True)
        patch_workspace_paths(str(workspace), source_workspace=str(parent.workspace))
        return workspace

    def _copy_agent_files(self, workspace: Path) -> None:
        for logical_path, source in self._agent_files.items():
            destination = resolve_workspace_path(workspace, logical_path)
            if not source.is_file():
                raise FileNotFoundError(f"agent configuration file is missing: {source}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def _build_adapter(self, *, trial: PlannedTrial, workspace: Path) -> Adapter:
        builder = self._adapter_builder
        if builder is None:
            from aec_bench.adapters.local_registry import build_local_adapter

            builder = build_local_adapter
        trajectory_writer = TrajectoryWriter(path=str(workspace / "trajectory.jsonl"))
        return builder(
            adapter_kind=trial.agent.adapter,
            model_name=trial.agent.model,
            workspace=str(workspace),
            trajectory_writer=trajectory_writer,
            constitutional_model=self._constitutional_model,
        )

    def _build_request(
        self,
        *,
        task: ResolvedTaskInstance,
        trial: PlannedTrial,
        workspace: Path,
        instruction: str | None,
    ) -> AdapterRequest:
        selected_instruction = instruction if instruction is not None else read_instruction(str(workspace))
        if not selected_instruction:
            raise ValueError("task workspace does not contain an instruction")
        system_prompt = trial.agent.system_prompt
        if trial.agent.system_prompt_file is not None:
            system_prompt = resolve_workspace_path(workspace, trial.agent.system_prompt_file).read_text(
                encoding="utf-8"
            )
        tools: list[ToolSpec] = []
        if trial.agent.adapter == "tool_loop":
            tools = [ToolSpec(name="bash", source="builtin", description="Execute a bash command in the workspace")]
        configuration = dict(trial.agent.parameters)
        timeout = trial.compute.timeout_override or task.task.timeout_seconds
        if trial.agent.adapter == "prime-agent":
            configuration["timeout_seconds"] = timeout
        elif trial.agent.adapter == "deepseek_harness":
            configuration["timeout_sec"] = timeout
        output_path = task.task.verifier.expected_output_path
        return AdapterRequest(
            instruction=selected_instruction,
            system_prompt=system_prompt,
            tools=tools,
            configuration=configuration,
            output_path=output_path,
            output_format="markdown" if Path(output_path).suffix.lower() == ".md" else "jsonl",
        )


def resolve_workspace_path(workspace: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if path.parts and path.parts[0] == "workspace":
        path = Path(*path.parts[1:])
    elif path.is_absolute() and path.parts[:2] == ("/", "workspace"):
        path = Path(*path.parts[2:])
    elif path.is_absolute() and path.parts[:2] == ("/", "logs"):
        path = Path(*path.parts[1:])
    elif path.is_absolute():
        raise ValueError("task output path must resolve inside the attempt workspace")
    candidate = (workspace / path).resolve()
    if candidate != workspace.resolve() and workspace.resolve() not in candidate.parents:
        raise ValueError("task output path must resolve inside the attempt workspace")
    return candidate


def load_canonical_refs(task_toml_path: Path) -> CanonicalRefSet:
    if not task_toml_path.exists():
        return CanonicalRefSet()
    import tomllib

    data = tomllib.loads(task_toml_path.read_text(encoding="utf-8"))
    return parse_canonical_refs(data.get("canonical_refs", {}))


def apply_normalisation(
    output_path: Path,
    refs: CanonicalRefSet,
    report_path: Path,
    *,
    committed_result: AdapterResult | None = None,
) -> NormalisationResult:
    text = output_path.read_text(encoding="utf-8")
    result = normalise_output(text, refs)
    if result.substitutions_count == 0:
        return result
    if committed_result is not None and committed_result.completion_commit is not None:
        raise ValueError("canonical-reference normalisation cannot change committed output bytes")
    output_path.write_text(result.normalised, encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "substitutions_count": result.substitutions_count,
                "audit_log": [
                    {
                        "matched_text": match.matched_text,
                        "canonical_value": match.canonical_value,
                        "distance": match.distance,
                        "count": match.count,
                    }
                    for match in result.audit_log
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return result


def validate_output_commit(*, result: AdapterResult, output_path: Path, expected_output_path: str) -> None:
    attestation = result.completion_commit
    if attestation is None:
        return
    if attestation.output_path != expected_output_path:
        raise ValueError("output commit path does not match the task expected output path")
    content = output_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != attestation.output_sha256:
        raise ValueError("output commit SHA-256 does not match the attempt output")
    if len(content) != attestation.output_size_bytes:
        raise ValueError("output commit byte size does not match the attempt output")


def _write_agent_result(
    *,
    workspace: Path,
    requested_model: str,
    adapter_kind: str,
    result: AdapterResult,
    output_source: str,
) -> None:
    payload = {
        "status": result.agent_output.status.value,
        "model": requested_model,
        "resolved_model": result.resolved_model,
        "adapter": adapter_kind,
        "adapter_configuration": result.configuration_record,
        "model_calls": result.usage_model_calls,
        "input_tokens": result.usage_input_tokens,
        "output_tokens": result.usage_output_tokens,
        "cache_read_tokens": result.usage_cache_read_tokens,
        "cache_write_tokens": result.usage_cache_write_tokens,
        "turns_used": result.turns_used,
        "max_turns": result.max_turns,
        "failure_kind": result.failure_kind.value if result.failure_kind is not None else None,
        "provider_error": result.provider_error,
        "output_source": output_source,
    }
    (workspace / "agent_result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def single_attempt() -> AttemptRecipe:
    def recipe(run_once: AttemptRunner) -> AttemptSelection:
        attempt = run_once(attempt_id="attempt-0")
        return AttemptSelection.selected(attempt, reason="single attempt")

    return recipe


def self_select() -> AttemptSelector:
    """Select the first eligible candidate with deterministic index tie-breaking."""

    def selector(candidates: Sequence[SelectorCandidate]) -> SelectorDecision:
        selected = next((candidate for candidate in candidates if candidate.eligible), None)
        return SelectorDecision(
            selected_index=None if selected is None else selected.index,
            reason=("no candidate completed with a primary output" if selected is None else "first eligible candidate"),
            configuration={"policy": "first_eligible", "tie_break": "lowest_candidate_index"},
        )

    return selector


def best_of(*, k: int, selector: AttemptSelector) -> AttemptRecipe:
    if k < 1:
        raise ValueError("best-of candidate count must be positive")
    if k == 1:
        return single_attempt()

    def recipe(run_once: AttemptRunner) -> AttemptSelection:
        attempts = [run_once(attempt_id=f"attempt-{index}") for index in range(k)]
        candidates = tuple(_selector_candidate(index=index, attempt=attempt) for index, attempt in enumerate(attempts))
        decision = selector(candidates)
        if decision.selected_index is not None and not 0 <= decision.selected_index < len(attempts):
            raise ValueError("selector returned an out-of-range candidate index")
        selected = None if decision.selected_index is None else attempts[decision.selected_index]
        if selected is not None and not candidates[decision.selected_index].eligible:
            raise ValueError("selector returned an ineligible candidate")
        evidence = AttemptSelectionEvidence(
            candidates=tuple(
                CandidateAttemptEvidence(
                    index=candidate.index,
                    attempt_id=candidate.attempt_id,
                    status=candidate.status,
                    elapsed_seconds=attempts[candidate.index].elapsed_seconds,
                    eligible=candidate.eligible,
                    selector_visible_output=candidate.output_reference,
                )
                for candidate in candidates
            ),
            selector=SelectorEvidence(
                configuration=dict(decision.configuration),
                model_calls=decision.model_calls,
                input_tokens=decision.input_tokens,
                output_tokens=decision.output_tokens,
                cache_read_tokens=decision.cache_read_tokens,
                cache_write_tokens=decision.cache_write_tokens,
                selected_index=decision.selected_index,
            ),
            decision="failed" if selected is None else "selected",
            reason=decision.reason,
            selected_index=decision.selected_index,
        )
        if selected is None:
            return AttemptSelection.failed(reason=decision.reason, evidence=evidence)
        return AttemptSelection.selected(selected, reason=decision.reason, evidence=evidence)

    return recipe


def build_attempt_recipe(spec: AttemptRecipeSpec) -> AttemptRecipe:
    if isinstance(spec, SingleAttemptSpec):
        return single_attempt()
    if isinstance(spec, BestOfSpec):
        return best_of(k=spec.candidates, selector=self_select())
    raise TypeError(f"unsupported attempt recipe specification: {type(spec).__name__}")


def _selector_candidate(*, index: int, attempt: TaskAttempt) -> SelectorCandidate:
    output_path = resolve_workspace_path(attempt.workspace, attempt.request.output_path)
    content = output_path.read_bytes() if output_path.is_file() else None
    reference = None
    if content:
        reference = ArtifactReference(
            kind="primary_output",
            path=attempt.request.output_path,
            sha256=hashlib.sha256(content).hexdigest(),
            media_type="application/octet-stream",
        )
    return SelectorCandidate(
        index=index,
        attempt_id=attempt.attempt_id,
        status=attempt.status,
        primary_output=content,
        output_reference=reference,
    )


def run_trial(
    *,
    runtime: LocalTaskRuntime,
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    recipe: AttemptRecipe,
    reviewer: ReviewerRunConfig | None = None,
    verify: bool = True,
    keep_workspaces: bool = False,
    selected_workspace_export: Path | None = None,
) -> TrialRecord:
    """Run one tracked recipe, verify its selection, and return durable trial evidence."""

    attempts: list[TaskAttempt] = []
    attempt_ids: set[str] = set()
    snapshot_dir: Path | None = None
    started = time.monotonic()
    first_workspace_index = len(runtime.attempt_workspaces)

    def tracked_run_once(
        *,
        attempt_id: str,
        parent: TaskAttempt | None = None,
        instruction: str | None = None,
    ) -> TaskAttempt:
        if not attempt_id.strip():
            raise ValueError("attempt_id must not be blank")
        if attempt_id in attempt_ids:
            raise ValueError(f"attempt_id must be unique within a trial: {attempt_id}")
        if parent is not None and all(parent is not item for item in attempts):
            raise ValueError("parent attempt was not created by this trial runner")
        attempt_ids.add(attempt_id)
        attempt = runtime.run_once(
            task,
            trial,
            attempt_id=attempt_id,
            parent=parent,
            instruction=instruction,
        )
        attempts.append(attempt)
        return attempt

    try:
        selection = recipe(tracked_run_once)
        selected = selection.attempt
        if selected is None:
            if not attempts:
                raise ValueError(f"attempt recipe did not create or select an attempt: {selection.reason}")
            return _build_failed_materialized_record(
                runtime=runtime,
                task=task,
                trial=trial,
                attempts=attempts,
                selection=selection,
                started=started,
            )
        if all(selected is not item for item in attempts):
            raise ValueError("attempt recipe selected an untracked attempt")

        snapshot_dir = Path(tempfile.mkdtemp(prefix="aec-bench-selected-", dir=runtime.artifact_root.parent))
        shutil.copytree(selected.workspace, snapshot_dir, dirs_exist_ok=True)
        if selected_workspace_export is not None:
            _export_selected_workspace(snapshot_dir, selected_workspace_export)
        evaluation, verification_seconds, verifier_receipt, evaluation_status = _evaluate_selected_attempt(
            task=task,
            attempt=selected,
            verify=verify,
        )
        if reviewer is not None and reviewer.enabled:
            review_result = run_workspace_reviewer(
                task_dir=task.instance_dir,
                workspace_dir=selected.workspace,
                config=reviewer,
            )
            if review_result.status != "complete" and reviewer.fail_on_error:
                raise RuntimeError(f"workspace reviewer failed: {review_result.status}")
            evaluation = _with_reviewer_summary(evaluation, selected.workspace)

        return _build_materialized_record(
            runtime=runtime,
            task=task,
            trial=trial,
            selected=selected,
            attempts=attempts,
            evaluation=evaluation,
            started=started,
            verification_seconds=verification_seconds,
            actor_snapshot=snapshot_dir,
            evidence_workspace=selected.workspace,
            selection_evidence=selection.evidence,
            verifier_receipt=verifier_receipt,
            evaluation_status=evaluation_status,
        )
    finally:
        if snapshot_dir is not None:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        if not keep_workspaces:
            for workspace in runtime.attempt_workspaces[first_workspace_index:]:
                shutil.rmtree(workspace, ignore_errors=True)


def _export_selected_workspace(snapshot: Path, destination: Path) -> None:
    """Atomically export the exact actor snapshot before verification changes the workspace."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise ValueError(f"selected workspace export destination must be empty: {destination}")
        destination.rmdir()
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        shutil.copytree(snapshot, staging, dirs_exist_ok=True)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def run_experiment(
    *,
    runtime: LocalTaskRuntime | ImportedExperimentRuntime,
    tasks: Sequence[ResolvedTaskInstance],
    trials: Sequence[PlannedTrial],
    recipe: AttemptRecipe | AttemptRecipeSpec,
    reviewer: ReviewerRunConfig | None = None,
    verify: bool = True,
    keep_workspaces: bool = False,
) -> list[TrialRecord]:
    """Apply one attempt recipe directly to every planned artifact-task trial."""

    if not isinstance(runtime, LocalTaskRuntime):
        if not isinstance(recipe, SingleAttemptSpec | BestOfSpec):
            raise TypeError("imported experiment runtimes require an AttemptRecipeSpec")
        return runtime.run_experiment(
            tasks=tasks,
            trials=trials,
            recipe_spec=recipe,
            reviewer=reviewer,
            verify=verify,
        )

    selected_recipe = build_attempt_recipe(recipe) if isinstance(recipe, SingleAttemptSpec | BestOfSpec) else recipe

    tasks_by_id: dict[str, ResolvedTaskInstance] = {}
    for task in tasks:
        task_id = task.task.task_id
        if task_id in tasks_by_id:
            raise ValueError(f"resolved tasks must have unique task ids: {task_id}")
        tasks_by_id[task_id] = task
        runtime.task_revision(task)

    records: list[TrialRecord] = []
    for trial in trials:
        task = tasks_by_id.get(trial.task_id)
        if task is None:
            raise ValueError(f"planned trial references an unresolved task: {trial.task_id}")
        records.append(
            run_trial(
                runtime=runtime,
                task=task,
                trial=trial,
                recipe=selected_recipe,
                reviewer=reviewer,
                verify=verify,
                keep_workspaces=keep_workspaces,
            )
        )
    return records


def run_trial_with_verifier_feedback(
    *,
    runtime: LocalTaskRuntime,
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    reviewer: ReviewerRunConfig | None = None,
    keep_workspace: bool = False,
    target_reward: float = _VERIFIER_RETRY_TARGET_REWARD,
) -> TrialRecord:
    """Run one optional reward-aware second pass in the first attempt workspace."""

    attempts: list[TaskAttempt] = []
    snapshot_dir: Path | None = None
    started = time.monotonic()
    first_workspace_index = len(runtime.attempt_workspaces)
    try:
        first = runtime.run_once(task, trial, attempt_id="attempt-0")
        attempts.append(first)
        (
            initial_evaluation,
            first_verification_seconds,
            first_verifier_receipt,
            first_evaluation_status,
        ) = _evaluate_selected_attempt(
            task=task,
            attempt=first,
            verify=True,
        )
        selected = first
        evaluation = initial_evaluation
        verification_seconds = first_verification_seconds

        if _should_run_verifier_feedback_retry(
            first.workspace,
            reward=initial_evaluation.reward,
            target_reward=target_reward,
        ):
            retry_instruction = _build_verifier_retry_instruction(
                workspace=first.workspace,
                output_path=resolve_workspace_path(first.workspace, task.task.verifier.expected_output_path),
                base_instruction=first.request.instruction,
                reward=initial_evaluation.reward,
            )
            _prepare_verifier_retry_workspace(
                workspace=first.workspace,
                output_path=resolve_workspace_path(first.workspace, task.task.verifier.expected_output_path),
                attempt_name="attempt-01",
            )
            shutil.rmtree(first.workspace / "tests", ignore_errors=True)
            for evidence_path in (
                task.task.verifier.reward_path,
                task.task.verifier.details_path,
                "logs/verifier/feedback.md",
            ):
                if evidence_path is None:
                    continue
                resolve_workspace_path(first.workspace, evidence_path).unlink(missing_ok=True)

            selected = runtime._run_again(
                task,
                trial,
                attempt_id="attempt-1",
                parent=first,
                instruction=retry_instruction,
            )
            attempts.append(selected)
            snapshot_dir = Path(tempfile.mkdtemp(prefix="aec-bench-selected-", dir=runtime.artifact_root.parent))
            shutil.copytree(selected.workspace, snapshot_dir, dirs_exist_ok=True)
            evaluation, second_verification_seconds, verifier_receipt, evaluation_status = _evaluate_selected_attempt(
                task=task,
                attempt=selected,
                verify=True,
            )
            verification_seconds = (first_verification_seconds or 0.0) + (second_verification_seconds or 0.0)
            _write_verifier_retry_summary(
                selected.workspace,
                {
                    "performed": True,
                    "initial_reward": initial_evaluation.reward,
                    "final_reward": evaluation.reward,
                    "retry_agent_seconds": selected.elapsed_seconds,
                    "retry_verifier_seconds": second_verification_seconds,
                },
            )
        else:
            snapshot_dir = Path(tempfile.mkdtemp(prefix="aec-bench-selected-", dir=runtime.artifact_root.parent))
            shutil.copytree(selected.workspace, snapshot_dir, dirs_exist_ok=True)
            verifier_receipt = first_verifier_receipt
            evaluation_status = first_evaluation_status

        if reviewer is not None and reviewer.enabled:
            review_result = run_workspace_reviewer(
                task_dir=task.instance_dir,
                workspace_dir=selected.workspace,
                config=reviewer,
            )
            if review_result.status != "complete" and reviewer.fail_on_error:
                raise RuntimeError(f"workspace reviewer failed: {review_result.status}")
            evaluation = _with_reviewer_summary(evaluation, selected.workspace)

        return _build_materialized_record(
            runtime=runtime,
            task=task,
            trial=trial,
            selected=selected,
            attempts=attempts,
            evaluation=evaluation,
            started=started,
            verification_seconds=verification_seconds,
            actor_snapshot=snapshot_dir,
            evidence_workspace=selected.workspace,
            verifier_receipt=verifier_receipt,
            evaluation_status=evaluation_status,
        )
    finally:
        if snapshot_dir is not None:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        if not keep_workspace:
            for workspace in runtime.attempt_workspaces[first_workspace_index:]:
                shutil.rmtree(workspace, ignore_errors=True)


def _build_materialized_record(
    *,
    runtime: LocalTaskRuntime,
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    selected: TaskAttempt,
    attempts: list[TaskAttempt],
    evaluation: EvaluationResult,
    started: float,
    verification_seconds: float | None,
    actor_snapshot: Path,
    evidence_workspace: Path,
    selection_evidence: AttemptSelectionEvidence | None = None,
    verifier_receipt: VerifierExecutionReceipt | None = None,
    evaluation_status: EvaluationStatus | None = None,
) -> TrialRecord:
    output_path = resolve_workspace_path(actor_snapshot, task.task.verifier.expected_output_path)
    record = build_trial_record(
        trial_id=trial.trial_id,
        experiment_id=trial.experiment_id,
        task=task.task,
        task_revision=runtime.task_revision(task),
        request=selected.request,
        result=_aggregate_attempt_usage(
            selected=selected.result,
            attempts=attempts,
            selection_evidence=selection_evidence,
        ),
        evaluation=evaluation,
        total_seconds=time.monotonic() - started,
        agent_seconds=sum(attempt.elapsed_seconds for attempt in attempts),
        verification_seconds=verification_seconds,
        runtime_image="local",
        compute_backend=trial.compute.backend,
        raw_output_path=str(output_path) if output_path.is_file() else None,
        conversation_path=_existing_path(actor_snapshot / "conversation.jsonl"),
        trajectory_path=_existing_path(actor_snapshot / "trajectory.jsonl"),
        attempt=trial.repetition,
        extensions=_trial_extensions(trial, selection_evidence, verifier_receipt),
        evaluation_status=evaluation_status,
    )
    _attach_workspace_files(record=record, workspace=actor_snapshot)
    _attach_post_execution_files(record=record, workspace=evidence_workspace)
    return materialize_trial_record(artifact_root=runtime.artifact_root, record=record)


def _build_failed_materialized_record(
    *,
    runtime: LocalTaskRuntime,
    task: ResolvedTaskInstance,
    trial: PlannedTrial,
    attempts: list[TaskAttempt],
    selection: AttemptSelection,
    started: float,
) -> TrialRecord:
    representative = attempts[0]
    record = build_trial_record(
        trial_id=trial.trial_id,
        experiment_id=trial.experiment_id,
        task=task.task,
        task_revision=runtime.task_revision(task),
        request=representative.request,
        result=_aggregate_attempt_usage(
            selected=representative.result,
            attempts=attempts,
            selection_evidence=selection.evidence,
        ),
        evaluation=None,
        total_seconds=time.monotonic() - started,
        agent_seconds=sum(attempt.elapsed_seconds for attempt in attempts),
        verification_seconds=None,
        runtime_image="local",
        compute_backend=trial.compute.backend,
        attempt=trial.repetition,
        extensions=_trial_extensions(trial, selection.evidence),
        execution_status_override=ExecutionStatus.FAILED,
        include_output=False,
    )
    return materialize_trial_record(artifact_root=runtime.artifact_root, record=record)


def _trial_extensions(
    trial: PlannedTrial,
    selection_evidence: AttemptSelectionEvidence | None,
    verifier_receipt: VerifierExecutionReceipt | None = None,
) -> dict[str, BaseModel]:
    extensions = dict(trial.extensions)
    if selection_evidence is not None:
        if "attempt_selection" in extensions:
            raise ValueError("planned trial extension conflicts with attempt selection evidence")
        extensions["attempt_selection"] = selection_evidence
    if verifier_receipt is not None:
        if "verifier_execution" in extensions:
            raise ValueError("planned trial extension conflicts with verifier execution evidence")
        extensions["verifier_execution"] = verifier_receipt
    return extensions


def _read_optional_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _should_run_verifier_feedback_retry(
    workspace: Path,
    *,
    reward: float | None,
    target_reward: float,
) -> bool:
    return reward is not None and reward < target_reward and (workspace / _VERIFIER_RETRY_PROMPT).is_file()


def _build_verifier_retry_instruction(
    *, workspace: Path, output_path: Path, base_instruction: str, reward: float
) -> str:
    verifier_dir = workspace / "logs" / "verifier"
    retry_instruction = _read_optional_text(workspace / "verifier_retry_instruction.md").strip()
    governing_instruction = retry_instruction or base_instruction.strip()
    parts = [
        governing_instruction,
        "---",
        "# Verifier Feedback Retry",
        _read_optional_text(workspace / _VERIFIER_RETRY_PROMPT).strip(),
        f"Previous verifier reward: `{reward:.4f}`.",
        "The previous output was:",
        "```markdown",
        _read_optional_text(output_path).strip(),
        "```",
    ]
    feedback = _read_optional_text(verifier_dir / "feedback.md").strip()
    details = _read_optional_text(verifier_dir / "details.json").strip()
    if feedback:
        parts.extend(("The verifier feedback was:", "```markdown", feedback, "```"))
    if details:
        parts.extend(("The verifier detail scores were:", "```json", details, "```"))
    parts.append(
        "Repair the workspace now. You may overwrite the required output and any required side-effect files. "
        "Do not merely describe files that should be written."
    )
    return "\n\n".join(part for part in parts if part)


def _is_verifier_retry_side_effect(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix == ".json"
        and not path.name.startswith(_VERIFIER_RETRY_EXCLUDED_PREFIXES)
        and path.name.endswith(_VERIFIER_RETRY_ARTIFACT_SUFFIXES)
    )


def _archive_verifier_retry_attempt(workspace: Path, output_path: Path, attempt_name: str) -> Path:
    archive_dir = workspace / "logs" / "verifier" / "attempts" / attempt_name
    archive_dir.mkdir(parents=True, exist_ok=True)
    for relative in (
        "agent_result.json",
        "trajectory.jsonl",
        "conversation.jsonl",
        "prime-events.jsonl",
        "prime-stderr.log",
        "prime-run.json",
        "logs/verifier/reward.json",
        "logs/verifier/details.json",
        "logs/verifier/feedback.md",
    ):
        source = workspace / relative
        if source.is_file():
            shutil.copy2(source, archive_dir / source.name)
    if output_path.is_file():
        shutil.copy2(output_path, archive_dir / output_path.name)
    prime_sessions = workspace / "logs" / "prime" / "sessions"
    if prime_sessions.is_dir():
        shutil.copytree(prime_sessions, archive_dir / "prime-sessions", dirs_exist_ok=True)
    for source in sorted(workspace.iterdir()):
        if _is_verifier_retry_side_effect(source):
            artifact_dir = archive_dir / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, artifact_dir / source.name)
    return archive_dir


def _prepare_verifier_retry_workspace(*, workspace: Path, output_path: Path, attempt_name: str) -> Path:
    archive_dir = _archive_verifier_retry_attempt(workspace, output_path, attempt_name)
    output_path.unlink(missing_ok=True)
    return archive_dir


def _write_verifier_retry_summary(workspace: Path, payload: Mapping[str, object]) -> None:
    retry_path = workspace / "logs" / "verifier" / "retry.json"
    retry_path.parent.mkdir(parents=True, exist_ok=True)
    retry_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _evaluate_selected_attempt(
    *, task: ResolvedTaskInstance, attempt: TaskAttempt, verify: bool
) -> tuple[EvaluationResult, float | None, VerifierExecutionReceipt | None, EvaluationStatus | None]:
    output_path = resolve_workspace_path(attempt.workspace, task.task.verifier.expected_output_path)
    verifier_seconds = None
    verifier_receipt = None
    reward_payload: dict[str, Any] | None = None
    details_payload: dict[str, Any] | None = None
    if verify:
        stage_verifier_assets(task.instance_dir, attempt.workspace)
        started = time.monotonic()
        transform_version = localise_staged_verifier_paths(
            workspace=attempt.workspace,
            verifier_root=attempt.workspace / "tests",
        )
        execution = execute_verifier(
            verifier_path=attempt.workspace / task.task.verifier.script,
            workspace=attempt.workspace,
            output_path=output_path,
            reward_path=resolve_workspace_path(attempt.workspace, task.task.verifier.reward_path),
            details_path=(
                None
                if task.task.verifier.details_path is None
                else resolve_workspace_path(attempt.workspace, task.task.verifier.details_path)
            ),
            verifier_key=f"{task.task.task_id}/verifier",
            verifier_version=VERIFIER_PROTOCOL_VERSION,
            runtime_transform_version=transform_version,
        )
        verifier_seconds = time.monotonic() - started
        verifier_receipt = execution.receipt
        reward_payload = execution.reward_payload
        details_payload = execution.details_payload
    verifier_completed = verifier_receipt is not None and verifier_receipt.completed
    output_present = output_path.is_file()
    valid_output = attempt.status is AgentOutputStatus.COMPLETED and output_present
    reward = 0.0
    breakdown = details_payload
    errors: list[str] = []
    if verifier_completed and reward_payload is not None:
        reward = float(reward_payload["reward"])
    elif not verify:
        errors.append("verification was disabled")
    elif verifier_receipt is not None:
        errors.append(verifier_receipt.failure_message or "verifier did not complete successfully")
    else:
        errors.append("verifier did not run")
    if not valid_output and reward != 0.0:
        errors.append("verifier reward was ignored because the selected attempt has no valid output")
        reward = 0.0
    evaluation = EvaluationResult(
        reward=reward,
        validity=ValidityCheck(
            output_parseable=valid_output,
            schema_valid=valid_output,
            verifier_completed=verifier_completed,
            errors=errors,
        ),
        breakdown=breakdown,
    )
    if verifier_receipt is not None:
        mapped = map_verifier_execution(
            receipt=verifier_receipt,
            evaluation=evaluation,
            expected_verifier_key=f"{task.task.task_id}/verifier",
            expected_verifier_version=VERIFIER_PROTOCOL_VERSION,
        )
        return mapped.evaluation, verifier_seconds, verifier_receipt, mapped.status
    return evaluation, verifier_seconds, verifier_receipt, None


def _with_reviewer_summary(evaluation: EvaluationResult, workspace: Path) -> EvaluationResult:
    summary_path = workspace / "logs" / "reviewer" / "summary.json"
    if not summary_path.is_file():
        return evaluation
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    breakdown = dict(evaluation.breakdown or {})
    breakdown["llm_reviewer"] = payload
    return evaluation.model_copy(update={"breakdown": breakdown})


def _attach_workspace_files(*, record: TrialRecord, workspace: Path) -> None:
    named_paths = {
        Path(value).resolve() for value, _media, _logical in record.pending_artifacts.values() if Path(value).is_file()
    }
    for path in sorted(candidate for candidate in workspace.rglob("*") if candidate.is_file()):
        if path.resolve() in named_paths or path.stat().st_size == 0:
            continue
        relative = path.relative_to(workspace).as_posix()
        record.attach_artifact(
            f"output:workspace:{relative}",
            path,
            media_type="application/octet-stream",
            logical_path=relative,
        )


def _attach_post_execution_files(*, record: TrialRecord, workspace: Path) -> None:
    for root in (workspace / "logs" / "verifier", workspace / "logs" / "reviewer"):
        if not root.is_dir():
            continue
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            if path.stat().st_size == 0:
                continue
            relative = path.relative_to(workspace).as_posix()
            record.attach_artifact(
                f"output:evidence:{relative}",
                path,
                media_type="application/octet-stream",
                logical_path=relative,
            )


def _existing_path(path: Path) -> str | None:
    return str(path) if path.is_file() else None


def _aggregate_attempt_usage(
    *,
    selected: AdapterResult,
    attempts: list[TaskAttempt],
    selection_evidence: AttemptSelectionEvidence | None = None,
) -> AdapterResult:
    usage_fields = (
        "usage_model_calls",
        "usage_input_tokens",
        "usage_output_tokens",
        "usage_cache_read_tokens",
        "usage_cache_write_tokens",
        "usage_advisor_calls",
        "usage_advisor_input_tokens",
        "usage_advisor_output_tokens",
    )
    updates: dict[str, int | None] = {}
    selector_usage = None if selection_evidence is None else selection_evidence.selector
    for field_name in usage_fields:
        values = [getattr(attempt.result, field_name) for attempt in attempts]
        selector_field = {
            "usage_model_calls": "model_calls",
            "usage_input_tokens": "input_tokens",
            "usage_output_tokens": "output_tokens",
            "usage_cache_read_tokens": "cache_read_tokens",
            "usage_cache_write_tokens": "cache_write_tokens",
        }.get(field_name)
        selector_value = (
            0 if selector_usage is None or selector_field is None else getattr(selector_usage, selector_field)
        )
        updates[field_name] = (
            None
            if all(value is None for value in values) and selector_value == 0
            else sum(value or 0 for value in values) + selector_value
        )
    return replace(selected, **updates)


__all__ = (
    "AttemptRecipeSpec",
    "AttemptRecipe",
    "AttemptRunner",
    "AttemptSelection",
    "AttemptSelectionEvidence",
    "AttemptSelector",
    "BestOfSpec",
    "CandidateAttemptEvidence",
    "ImportedExperimentRuntime",
    "LocalTaskRuntime",
    "SelectorCandidate",
    "SelectorDecision",
    "SelfSelectorSpec",
    "SingleAttemptSpec",
    "TaskAttempt",
    "best_of",
    "build_attempt_recipe",
    "run_experiment",
    "run_trial",
    "run_trial_with_verifier_feedback",
    "self_select",
    "single_attempt",
)
