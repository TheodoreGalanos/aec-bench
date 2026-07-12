# ABOUTME: Adapts persistent evidence lifecycles to the local Verifiers StatefulToolEnv API.
# ABOUTME: Reuses host-controlled tools and invokes only the task-owned terminal verifier for reward.

from __future__ import annotations

import importlib
import json
import random
import tempfile
from pathlib import Path
from typing import Any, cast

from aec_bench.meta_harness.evidence_lifecycle import (
    evidence_lifecycle_package_identity,
    fail_checkpoint_attempt,
    load_evidence_lifecycle_spec,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import LifecycleVisibilityPolicy
from aec_bench.meta_harness.evidence_lifecycle_experiment import repository_provenance
from aec_bench.meta_harness.evidence_lifecycle_local import (
    EvidenceLifecycleControlTool,
    EvidenceLifecycleWorkspaceTool,
)
from aec_bench.meta_harness.evidence_lifecycle_state import CheckpointAttemptStatus
from aec_bench.prime_lab.lifecycle_exporter import (
    PrimeLifecycleExportManifest,
    PrimeLifecyclePackageRecord,
    PrimeLifecycleSourceProvenance,
    load_prime_lifecycle_manifest,
)
from aec_bench.task_world_templates.lifecycles import lifecycle_package_variant
from aec_bench.task_world_templates.materializer import verify_template_lifecycle

_SYSTEM_PROMPT = """You are completing one staged AEC evidence lifecycle in a single persistent interaction.
Use only the lifecycle workspace and control tools. Review the currently released evidence, write the active
checkpoint JSON submission, and submit that checkpoint before continuing. Later evidence is unavailable until
the host releases it. Do not claim verification or reward; the task-owned verifier runs only after completion.
"""


def load_local_lifecycle_environment(
    *,
    manifest_path: Path,
    split: str = "eval",
    variant: str | list[str] | None = None,
    num_examples: int | None = None,
    seed: int | None = None,
    harness: str | None = None,
) -> Any:
    """Load one local-only persistent lifecycle environment from a strict manifest."""
    if split not in {"eval", "all"}:
        raise ValueError("local lifecycle exports support only split='eval' or split='all'")
    if harness not in {None, "persistent_lifecycle"}:
        raise ValueError("local lifecycle exports require harness='persistent_lifecycle'")
    if num_examples is not None and num_examples <= 0:
        raise ValueError("num_examples must be positive")

    manifest = load_prime_lifecycle_manifest(Path(manifest_path))
    _assert_source_provenance(manifest.source)
    records = _select_records(manifest, variant=variant, num_examples=num_examples, seed=seed)
    supports_evidence_requests = _records_support_evidence_requests(records)
    dataset = _build_dataset(records)
    vf = importlib.import_module("verifiers")
    rubric = _build_lifecycle_rubric(vf)
    environment_type = _build_environment_type(
        vf,
        supports_evidence_requests=supports_evidence_requests,
    )
    return environment_type(
        manifest=manifest,
        records=records,
        dataset=dataset,
        rubric=rubric,
    )


def list_workspace(path: str = ".", state: dict[str, Any] | None = None) -> str:
    """List an agent-visible directory in the current lifecycle workspace."""
    return _workspace_tool(state).list_workspace(path)


def read_workspace_file(path: str, state: dict[str, Any] | None = None) -> str:
    """Read one agent-visible file from the current lifecycle workspace."""
    return _workspace_tool(state).read_workspace_file(path)


def write_checkpoint_submission(
    checkpoint_id: str,
    content: str,
    state: dict[str, Any] | None = None,
) -> str:
    """Write the active checkpoint JSON through the host-confined workspace tool."""
    return _workspace_tool(state).write_checkpoint_submission(checkpoint_id, content)


def request_evidence(
    checkpoint_id: str,
    request_id: str,
    reason: str,
    state: dict[str, Any] | None = None,
) -> str:
    """Request one declared evidence packet through the session-bound host tool."""
    return _control_tool(_required_state(state)).request_evidence(
        checkpoint_id,
        request_id,
        reason,
    )


def submit_checkpoint(checkpoint_id: str, state: dict[str, Any] | None = None) -> str:
    """Archive one checkpoint and end the rollout only after terminal lifecycle completion."""
    resolved_state = _required_state(state)
    result = _control_tool(resolved_state).submit_checkpoint(checkpoint_id)
    payload = _json_object(result)
    resolved_state["lifecycle_status"] = payload.get("status")
    if payload.get("status") == "complete":
        resolved_state["final_env_response"] = [
            {
                "role": "user",
                "content": "The host accepted the final checkpoint and the lifecycle is complete.",
            }
        ]
    return result


def revisit_checkpoint(
    checkpoint_id: str,
    reason: str,
    state: dict[str, Any] | None = None,
) -> str:
    """Revisit one immutable prior checkpoint without rewinding lifecycle state."""
    return _control_tool(_required_state(state)).revisit_checkpoint(checkpoint_id, reason)


async def aec_bench_lifecycle_reward(state: dict[str, Any]) -> float:
    """Return task-owned terminal reward, or zero while closing an incomplete rollout."""
    package_dir = Path(_required_string(state, "package_dir"))
    run_dir = Path(_required_string(state, "run_dir"))
    source = PrimeLifecycleSourceProvenance.model_validate(state.get("lifecycle_source"))
    record = PrimeLifecyclePackageRecord.model_validate(state.get("lifecycle_package"))
    _assert_source_provenance(source)
    _assert_package_identity(record)
    lifecycle = read_evidence_lifecycle_state(package_dir, run_dir)
    if lifecycle["status"] != "complete":
        _close_incomplete_attempt(package_dir, run_dir, lifecycle)
        state["lifecycle_reward_status"] = "incomplete"
        state["aec_bench_reward"] = 0.0
        return 0.0

    verification = verify_template_lifecycle(package_dir, run_dir)
    reward = float(verification["reward"])
    state["lifecycle_verification"] = verification
    state["lifecycle_reward_status"] = "verified"
    state["aec_bench_reward"] = reward
    return reward


def _build_environment_type(
    vf: Any,
    *,
    supports_evidence_requests: bool,
) -> type[Any]:
    class AecBenchLifecycleEnv(vf.StatefulToolEnv):  # type: ignore[misc]
        execution_mode = "persistent_context"
        memory_visibility_policy = "persistent_context"

        def __init__(
            self,
            *,
            manifest: PrimeLifecycleExportManifest,
            records: tuple[PrimeLifecyclePackageRecord, ...],
            dataset: Any,
            rubric: Any,
        ) -> None:
            self.lifecycle_manifest = manifest
            self.lifecycle_records = records
            system_prompt = _SYSTEM_PROMPT
            if supports_evidence_requests:
                system_prompt += (
                    " Inspect the active checkpoint evidence-requests.json catalogue and use request_evidence "
                    "only when additional declared evidence is needed within its finite budget."
                )
            super().__init__(
                tools=[],
                max_turns=manifest.max_turns,
                dataset=dataset,
                eval_dataset=dataset,
                rubric=rubric,
                system_prompt=system_prompt,
            )
            tools = [
                list_workspace,
                read_workspace_file,
                write_checkpoint_submission,
            ]
            if supports_evidence_requests:
                tools.append(request_evidence)
            tools.extend([submit_checkpoint, revisit_checkpoint])
            for tool in tools:
                self.add_tool(tool, args_to_skip=["state"])

        async def setup_state(self, state: dict[str, Any]) -> None:
            record = PrimeLifecyclePackageRecord.model_validate(_info_payload(state.get("info")))
            if record not in self.lifecycle_records:
                raise ValueError("rollout lifecycle package is not declared by the export manifest")
            _assert_source_provenance(self.lifecycle_manifest.source)
            _assert_package_identity(record)
            session_id = _required_string(state, "trajectory_id")
            temporary = tempfile.TemporaryDirectory(prefix="aec-prime-lifecycle-")
            run_dir = Path(temporary.name) / "run"
            package_dir = Path(record.package_dir)
            try:
                initial = prepare_evidence_checkpoint(package_dir, run_dir)
                open_checkpoint_attempt(
                    package_dir,
                    run_dir,
                    session_id=session_id,
                    execution_mode="persistent_context",
                )
            except Exception:
                temporary.cleanup()
                raise
            state["aec_tempdir"] = temporary
            state["package_dir"] = str(package_dir)
            state["run_dir"] = str(run_dir)
            state["lifecycle_source"] = self.lifecycle_manifest.source.model_dump(mode="json")
            state["lifecycle_package"] = record.model_dump(mode="json")
            state["workspace_path"] = initial["workspace"]
            state["lifecycle_workspace_tool"] = EvidenceLifecycleWorkspaceTool(
                package_dir=package_dir,
                run_dir=run_dir,
                visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
            )
            state["lifecycle_control_tool"] = EvidenceLifecycleControlTool(
                package_dir=package_dir,
                run_dir=run_dir,
                session_id=session_id,
            )

        def update_tool_args(
            self,
            tool_name: str,
            tool_args: dict[str, Any],
            messages: list[Any],
            state: dict[str, Any],
            **kwargs: Any,
        ) -> dict[str, Any]:
            del messages, kwargs
            if tool_name not in self.tool_map:
                return tool_args
            tool_args["state"] = state
            return tool_args

    return AecBenchLifecycleEnv


def _build_lifecycle_rubric(vf: Any) -> Any:
    class AecBenchLifecycleRubric(vf.Rubric):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(funcs=[aec_bench_lifecycle_reward])

        @vf.cleanup  # type: ignore[untyped-decorator]
        async def cleanup_lifecycle_state(self, state: dict[str, Any]) -> None:
            temporary = state.pop("aec_tempdir", None)
            state.pop("lifecycle_workspace_tool", None)
            state.pop("lifecycle_control_tool", None)
            if temporary is not None:
                temporary.cleanup()

    return AecBenchLifecycleRubric()


def _build_dataset(records: tuple[PrimeLifecyclePackageRecord, ...]) -> Any:
    dataset_module = importlib.import_module("datasets")
    return dataset_module.Dataset.from_list(
        [
            {
                "prompt": [
                    {
                        "role": "user",
                        "content": (
                            "Complete this entire staged evidence lifecycle using the provided tools. "
                            "The first checkpoint instruction follows.\n\n"
                            f"{record.initial_instruction}"
                        ),
                    }
                ],
                "answer": record.variant_id,
                "info": json.dumps(record.model_dump(mode="json"), sort_keys=True),
            }
            for record in records
        ]
    )


def _select_records(
    manifest: PrimeLifecycleExportManifest,
    *,
    variant: str | list[str] | None,
    num_examples: int | None,
    seed: int | None,
) -> tuple[PrimeLifecyclePackageRecord, ...]:
    records = list(manifest.packages)
    if variant is not None:
        requested = {variant} if isinstance(variant, str) else set(variant)
        available = {record.variant_id for record in records}
        unknown = sorted(requested - available)
        if unknown:
            raise ValueError(f"unknown lifecycle variant(s): {', '.join(unknown)}")
        records = [record for record in records if record.variant_id in requested]
    if seed is not None:
        random.Random(seed).shuffle(records)
    if num_examples is not None:
        records = records[:num_examples]
    if not records:
        raise ValueError("lifecycle selection is empty")
    return tuple(records)


def _records_support_evidence_requests(
    records: tuple[PrimeLifecyclePackageRecord, ...],
) -> bool:
    capabilities = {
        any(
            checkpoint.conditional_evidence is not None
            for checkpoint in load_evidence_lifecycle_spec(Path(record.package_dir)).checkpoints
        )
        for record in records
    }
    if len(capabilities) != 1:
        raise ValueError("selected lifecycle packages must share one conditional evidence capability")
    return capabilities.pop()


def _assert_source_provenance(expected: PrimeLifecycleSourceProvenance) -> None:
    expected_root = Path(expected.root).resolve()
    runtime_file = Path(__file__).resolve()
    expected_packages = (expected_root / "src" / "aec_bench", expected_root / "aec_bench")
    if not any(runtime_file.is_relative_to(package) for package in expected_packages):
        raise ValueError("executing aec-bench runtime is outside lifecycle export source root")
    actual = PrimeLifecycleSourceProvenance.model_validate(repository_provenance(expected_root))
    if actual != expected:
        raise ValueError("local aec-bench source provenance does not match lifecycle export")


def _assert_package_identity(record: PrimeLifecyclePackageRecord) -> None:
    package_dir = Path(record.package_dir)
    actual = evidence_lifecycle_package_identity(package_dir)
    expected = {
        "lifecycle_id": record.lifecycle_id,
        "world_id": record.world_id,
        "spec_sha256": record.lifecycle_spec_sha256,
        "package_sha256": record.package_sha256,
    }
    try:
        variant = lifecycle_package_variant(package_dir)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"lifecycle package identity drift: {package_dir}") from exc
    if actual != expected or variant is None:
        raise ValueError(f"lifecycle package identity drift: {package_dir}")
    if variant.get("variant_id") != record.variant_id or variant.get("visibility") != record.visibility:
        raise ValueError(f"lifecycle package identity drift: {package_dir}")


def _close_incomplete_attempt(package_dir: Path, run_dir: Path, lifecycle: dict[str, Any]) -> None:
    active_checkpoint_id = lifecycle.get("active_checkpoint_id")
    if not isinstance(active_checkpoint_id, str):
        return
    checkpoint = next(
        (item for item in lifecycle.get("checkpoint_runs", []) if item.get("checkpoint_id") == active_checkpoint_id),
        None,
    )
    if not isinstance(checkpoint, dict):
        return
    attempts = checkpoint.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return
    attempt = attempts[-1]
    if not isinstance(attempt, dict) or attempt.get("status") != CheckpointAttemptStatus.ACTIVE.value:
        return
    session_id = attempt.get("session_id")
    if isinstance(session_id, str):
        fail_checkpoint_attempt(
            package_dir,
            run_dir,
            session_id=session_id,
            failure_kind="rollout_incomplete",
        )


def _workspace_tool(state: dict[str, Any] | None) -> EvidenceLifecycleWorkspaceTool:
    resolved = _required_state(state).get("lifecycle_workspace_tool")
    if not isinstance(resolved, EvidenceLifecycleWorkspaceTool):
        raise ValueError("lifecycle workspace tool is unavailable")
    return resolved


def _control_tool(state: dict[str, Any]) -> EvidenceLifecycleControlTool:
    resolved = state.get("lifecycle_control_tool")
    if not isinstance(resolved, EvidenceLifecycleControlTool):
        raise ValueError("lifecycle control tool is unavailable")
    return resolved


def _required_state(state: dict[str, Any] | None) -> dict[str, Any]:
    if state is None:
        raise ValueError("lifecycle rollout state is unavailable")
    return state


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"lifecycle state field is missing: {key}")
    return value


def _info_payload(info: object) -> dict[str, Any]:
    if isinstance(info, str):
        return _json_object(info)
    if isinstance(info, dict):
        return cast(dict[str, Any], info)
    raise ValueError("lifecycle dataset info is malformed")


def _json_object(payload: str) -> dict[str, Any]:
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("expected a JSON object")
    return cast(dict[str, Any], parsed)
