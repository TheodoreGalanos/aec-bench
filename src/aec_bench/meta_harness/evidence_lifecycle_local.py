# ABOUTME: Runs evidence lifecycles through persistent or fresh local agent sessions.
# ABOUTME: Preserves checkpoint attempts, revisits, trajectories, usage, and provider outcomes.

from __future__ import annotations

import inspect
import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.local_registry import LocalAdapterRegistry
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.ledger.durability import fsync_directory, mkdir_durable
from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    LifecycleEpisodeExecutionError,
    execute_lifecycle_operation,
    fail_checkpoint_attempt,
    load_evidence_lifecycle_spec,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
    request_evidence_checkpoint,
    revisit_evidence_checkpoint,
    run_evidence_lifecycle,
    submit_evidence_checkpoint,
    validate_evidence_checkpoint_submission,
    validate_lifecycle_verification,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleEpisodeContext,
    LifecycleEpisodeEnvironment,
    LifecycleEpisodeEnvironmentFailure,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleEpisodeUsage,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleExecutionMode as LifecycleExecutionMode,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleVisibilityPolicy as LifecycleVisibilityPolicy,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import (
    LifecycleExperimentRecorder,
    LifecycleExperimentSweepContext,
    record_lifecycle_experiment,
)
from aec_bench.trajectory.writer import TrajectoryWriter


@dataclass(frozen=True)
class EvidenceLifecycleControlTool:
    """Host-controlled lifecycle actions exposed to one bound agent session."""

    package_dir: Path
    run_dir: Path
    session_id: str = "manual"

    def request_evidence(self, checkpoint_id: str, request_id: str, reason: str) -> str:
        """Request one declared evidence packet using the active checkpoint budget."""
        if not checkpoint_id.strip() or not request_id.strip() or not reason.strip():
            return json.dumps(
                {
                    "status": "rejected",
                    "error": "evidence request arguments must not be blank",
                }
            )
        result = request_evidence_checkpoint(
            self.package_dir,
            self.run_dir,
            checkpoint_id=checkpoint_id,
            request_id=request_id,
            reason=reason,
            session_id=self.session_id,
        )
        payload: dict[str, Any] = {
            "status": result["outcome"],
            "checkpoint_id": result["requested_checkpoint_id"],
            "request_id": result["request_id"],
            "remaining_budget": result["budget_after"],
        }
        if result["outcome"] in {"released", "already_released"}:
            payload["released_files"] = [artifact["workspace_path"] for artifact in result["released_artifacts"]]
        if result["rejection"] is not None:
            payload["rejection"] = result["rejection"]
        return json.dumps(payload)

    def execute_operation(
        self,
        checkpoint_id: str,
        operation_id: str,
        visible_source_state_sha256: str,
        reason: str,
    ) -> str:
        """Execute one declared operation against the named visible source state."""
        arguments = (checkpoint_id, operation_id, visible_source_state_sha256, reason)
        if any(not isinstance(argument, str) or not argument.strip() for argument in arguments):
            return json.dumps(
                {
                    "status": "rejected",
                    "error": "operation arguments must not be blank",
                }
            )
        if len(visible_source_state_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in visible_source_state_sha256
        ):
            return json.dumps(
                {
                    "status": "rejected",
                    "error": "visible source state sha256 must contain 64 lowercase hexadecimal characters",
                }
            )
        result = execute_lifecycle_operation(
            self.package_dir,
            self.run_dir,
            checkpoint_id=checkpoint_id,
            operation_id=operation_id,
            visible_source_state_sha256=visible_source_state_sha256,
            reason=reason,
            session_id=self.session_id,
        )
        return json.dumps(_operation_tool_response(result))

    def submit_checkpoint(self, checkpoint_id: str) -> str:
        """Submit the named checkpoint and release the next evidence packet.

        Write the current checkpoint JSON to its required submission path before
        calling this tool. A valid submission is archived immutably. If another
        checkpoint remains, the response contains its instruction and paths.
        """
        state = read_evidence_lifecycle_state(self.package_dir, self.run_dir)
        active_checkpoint_id = state.get("active_checkpoint_id")
        if checkpoint_id != active_checkpoint_id:
            return json.dumps(
                {
                    "status": "rejected",
                    "error": (f"active checkpoint is {active_checkpoint_id!r}; cannot submit {checkpoint_id!r}"),
                }
            )
        try:
            result = submit_evidence_checkpoint(
                self.package_dir,
                self.run_dir,
                episode_result={"mode": "persistent_session"},
            )
            if result["status"] != "complete":
                result = prepare_evidence_checkpoint(self.package_dir, self.run_dir)
                open_checkpoint_attempt(
                    self.package_dir,
                    self.run_dir,
                    session_id=self.session_id,
                    execution_mode="persistent_context",
                )
        except EvidenceLifecycleError as exc:
            return json.dumps({"status": "rejected", "error": str(exc)})
        return json.dumps(_tool_response(result))

    def revisit_checkpoint(self, checkpoint_id: str, reason: str) -> str:
        """Inspect and log an immutable prior checkpoint without rewinding state."""
        try:
            result = revisit_evidence_checkpoint(
                self.package_dir,
                self.run_dir,
                checkpoint_id=checkpoint_id,
                reason=reason,
            )
        except EvidenceLifecycleError as exc:
            return json.dumps({"status": "rejected", "error": str(exc)})
        return json.dumps({"status": "revisited", **result})


@dataclass(frozen=True)
class EvidenceLifecycleWorkspaceTool:
    """Expose only lifecycle-readable files and the active submission destination."""

    package_dir: Path
    run_dir: Path
    visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY

    def list_workspace(self, path: str = ".") -> str:
        """List one visible workspace directory without permitting path escape."""
        try:
            target, relative = self._read_path(path)
            if not target.is_dir():
                raise EvidenceLifecycleError(f"workspace directory not found: {relative}")
            entries = sorted(
                child.name
                for child in target.iterdir()
                if not child.name.startswith(".") and self._is_visible_path(PurePosixPath(relative) / child.name)
            )
        except EvidenceLifecycleError as exc:
            return json.dumps({"status": "rejected", "error": str(exc)})
        return json.dumps({"status": "ok", "path": relative, "entries": entries})

    def read_workspace_file(self, path: str) -> str:
        """Read one released or persisted review artifact inside the workspace."""
        try:
            target, relative = self._read_path(path)
            if not target.is_file():
                raise EvidenceLifecycleError(f"workspace file not found: {relative}")
            content = target.read_text(encoding="utf-8")
        except (EvidenceLifecycleError, OSError, UnicodeError) as exc:
            return json.dumps({"status": "rejected", "error": str(exc)})
        return json.dumps({"status": "ok", "path": relative, "content": content})

    def write_checkpoint_submission(self, checkpoint_id: str, content: str) -> str:
        """Write JSON only to the active checkpoint's declared submission path."""
        try:
            state = read_evidence_lifecycle_state(self.package_dir, self.run_dir)
            if state["active_checkpoint_id"] != checkpoint_id:
                raise EvidenceLifecycleError(
                    f"active checkpoint is {state['active_checkpoint_id']!r}; cannot write {checkpoint_id!r}"
                )
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise EvidenceLifecycleError("checkpoint submission must contain a JSON object")
            spec = load_evidence_lifecycle_spec(self.package_dir)
            checkpoint = next(item for item in spec.checkpoints if item.checkpoint_id == checkpoint_id)
            validate_evidence_checkpoint_submission(checkpoint, payload)
            destination = Path(state["workspace"]) / checkpoint.submission_path
            _write_json(destination, payload)
        except (EvidenceLifecycleError, json.JSONDecodeError, StopIteration) as exc:
            return json.dumps({"status": "rejected", "error": str(exc)})
        return json.dumps(
            {
                "status": "written",
                "checkpoint_id": checkpoint_id,
                "submission_path": str(destination),
            }
        )

    def _read_path(self, raw_path: str) -> tuple[Path, str]:
        if "\\" in raw_path:
            raise EvidenceLifecycleError("workspace path must use POSIX separators")
        path = PurePosixPath(raw_path or ".")
        if path.is_absolute() or ".." in path.parts:
            raise EvidenceLifecycleError("workspace path must stay inside the lifecycle workspace")
        relative = path.as_posix()
        if not self._is_visible_path(path):
            raise EvidenceLifecycleError(f"workspace path is not agent-readable: {relative}")
        workspace = (self.run_dir / "workspace").resolve()
        target = (workspace / path).resolve()
        if target != workspace and workspace not in target.parents:
            raise EvidenceLifecycleError("workspace path must stay inside the lifecycle workspace")
        return target, relative

    def _is_visible_path(self, path: PurePosixPath) -> bool:
        parts = tuple(part for part in path.parts if part not in {".", ""})
        if not parts:
            return True
        root = parts[0]
        if root == "instruction.md":
            return len(parts) == 1
        if root == "hydraulics":
            return len(parts) == 1 or (len(parts) == 2 and parts[1] == "current-source.json")
        if self.visibility_policy in {
            LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
            LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        }:
            return root in {"inbox", "submissions", "checkpoints", "branch_origin"}
        if self.visibility_policy == LifecycleVisibilityPolicy.RAW_EVIDENCE_ONLY:
            return root in {"inbox", "checkpoints"}
        if root not in {"inbox", "checkpoints"}:
            return False
        if len(parts) == 1:
            return True
        state = read_evidence_lifecycle_state(self.package_dir, self.run_dir)
        return bool(parts[1] == state["active_checkpoint_id"])


def run_local_evidence_lifecycle_session(
    *,
    package_dir: Path,
    run_dir: Path,
    model: str,
    verifier: Any,
    adapter_kind: str = "tool_loop",
    max_turns: int = 60,
    process_id: str = "process.lifecycle",
    registry: Any | None = None,
    visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
    sweep_context: LifecycleExperimentSweepContext | None = None,
    repository_dir: Path | None = None,
    require_adapter_identity_match: bool = False,
    experiment_recorder: LifecycleExperimentRecorder | None = None,
    run_authorization_sha256: str | None = None,
) -> dict[str, Any]:
    """Run all checkpoints in one adapter execution and one model conversation."""
    if adapter_kind not in {"tool_loop", "pydantic_ai"}:
        raise ValueError("persistent evidence lifecycles require a native tool-loop adapter")
    if visibility_policy != LifecycleVisibilityPolicy.PERSISTENT_CONTEXT:
        raise ValueError("persistent sessions require persistent_context visibility")

    package = Path(package_dir)
    run = Path(run_dir)
    initial = prepare_evidence_checkpoint(
        package,
        run,
        run_authorization_sha256=run_authorization_sha256,
    )
    if initial["status"] == "complete":
        raise EvidenceLifecycleError("lifecycle run is already complete")
    _seal_interrupted_sessions(
        run=run,
        lifecycle=initial,
        model=model,
        adapter_kind=adapter_kind,
        max_turns=max_turns,
        execution_mode="persistent_context",
        memory_visibility_policy=visibility_policy.value,
    )

    session_id = _next_session_id(run)
    session_dir = run / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    trajectory_path = session_dir / "trajectory.jsonl"
    trajectory_writer = TrajectoryWriter(path=str(trajectory_path))
    open_checkpoint_attempt(
        package,
        run,
        session_id=session_id,
        execution_mode="persistent_context",
    )
    control = EvidenceLifecycleControlTool(package_dir=package, run_dir=run, session_id=session_id)
    workspace_tool = EvidenceLifecycleWorkspaceTool(
        package_dir=package,
        run_dir=run,
        visibility_policy=visibility_policy,
    )
    supports_evidence_requests = _supports_evidence_requests(package)
    supports_lifecycle_operations = _supports_lifecycle_operations(package)
    native_tools = [
        workspace_tool.list_workspace,
        workspace_tool.read_workspace_file,
        workspace_tool.write_checkpoint_submission,
    ]
    tool_specs = [
        ToolSpec(name="list_workspace", source="builtin", description="List visible lifecycle files."),
        ToolSpec(
            name="read_workspace_file",
            source="builtin",
            description="Read one visible lifecycle file.",
        ),
        ToolSpec(
            name="write_checkpoint_submission",
            source="builtin",
            description="Write the active checkpoint JSON submission.",
        ),
    ]
    if supports_evidence_requests:
        native_tools.append(control.request_evidence)
        tool_specs.append(
            ToolSpec(
                name="request_evidence",
                source="builtin",
                description="Request one declared evidence packet within the active checkpoint budget.",
            )
        )
    if supports_lifecycle_operations:
        native_tools.append(control.execute_operation)
        tool_specs.append(
            ToolSpec(
                name="execute_operation",
                source="builtin",
                description="Execute one declared operation against the current visible source state.",
            )
        )
    native_tools.extend([control.submit_checkpoint, control.revisit_checkpoint])
    tool_specs.extend(
        [
            ToolSpec(
                name="submit_checkpoint",
                source="builtin",
                description="Archive the active checkpoint and release the next evidence packet.",
            ),
            ToolSpec(
                name="revisit_checkpoint",
                source="builtin",
                description="Inspect and log an immutable prior checkpoint without rewinding the run.",
            ),
        ]
    )
    resolved_registry = registry or LocalAdapterRegistry()
    try:
        adapter = resolved_registry.build(
            adapter_kind=adapter_kind,
            model_name=model,
            workspace=initial["workspace"],
            trajectory_writer=trajectory_writer,
            native_tools=native_tools,
            enable_bash=False,
        )
        result = adapter.execute(
            AdapterRequest(
                instruction=_persistent_session_instruction(
                    initial,
                    supports_evidence_requests=supports_evidence_requests,
                    supports_lifecycle_operations=supports_lifecycle_operations,
                ),
                system_prompt=_workspace_policy(
                    initial,
                    persistent=True,
                    visibility_policy=visibility_policy,
                    supports_evidence_requests=supports_evidence_requests,
                    supports_lifecycle_operations=supports_lifecycle_operations,
                ),
                tools=tool_specs,
                configuration={"max_turns": max_turns},
                output_path=str(Path(initial["workspace"]) / "output.md"),
                output_format="markdown",
            )
        )
    except Exception as exc:
        fail_checkpoint_attempt(
            package,
            run,
            session_id=session_id,
            failure_kind="adapter_exception",
        )
        failed_agent_result = _failed_agent_result(
            model=model,
            adapter_kind=adapter_kind,
            max_turns=max_turns,
            session_id=session_id,
            provider_error=str(exc),
            memory_visibility_policy=visibility_policy.value,
        )
        lifecycle = read_evidence_lifecycle_state(package, run)
        failed_agent_result["checkpoint_ids"] = _session_checkpoint_ids(lifecycle, session_id)
        _write_json(session_dir / "agent_result.json", failed_agent_result)
        _build_local_task_run(
            package=package,
            run=run,
            process_id=process_id,
            lifecycle=lifecycle,
            verifier=verifier,
            agent=_normalized_agent_evidence(
                model=model,
                adapter_kind=adapter_kind,
                execution_mode="persistent_context",
                memory_visibility_policy=visibility_policy.value,
                max_turns=max_turns,
                sessions=_persistent_context_sessions(run),
                lifecycle=lifecycle,
            ),
            sweep_context=sweep_context,
            repository_dir=repository_dir,
            experiment_recorder=experiment_recorder,
        )
        raise
    finally:
        trajectory_writer.close()

    agent_result = _agent_result(
        result,
        model=model,
        adapter_kind=adapter_kind,
        max_turns=max_turns,
        session_id=session_id,
        memory_visibility_policy=visibility_policy.value,
    )
    returned_failure = (
        "adapter_identity_mismatch"
        if require_adapter_identity_match and agent_result["adapter_name"] != adapter_kind
        else _adapter_failure_kind(result)
    )
    if returned_failure is not None:
        agent_result["status"] = "failed"
        agent_result["failure_kind"] = returned_failure
    lifecycle = read_evidence_lifecycle_state(package, run)
    if returned_failure is not None and lifecycle["active_checkpoint_id"] is not None:
        fail_checkpoint_attempt(
            package,
            run,
            session_id=session_id,
            failure_kind=returned_failure,
        )
        lifecycle = read_evidence_lifecycle_state(package, run)
    if returned_failure is None and lifecycle["status"] != "complete":
        returned_failure = "lifecycle_incomplete"
        agent_result["status"] = "failed"
        agent_result["failure_kind"] = returned_failure
        fail_checkpoint_attempt(
            package,
            run,
            session_id=session_id,
            failure_kind=returned_failure,
        )
        lifecycle = read_evidence_lifecycle_state(package, run)
    agent_result["checkpoint_ids"] = _session_checkpoint_ids(lifecycle, session_id)
    _write_json(session_dir / "agent_result.json", agent_result)
    _write_conversation(session_dir / "conversation.jsonl", result.transcript)
    if result.raw_output_text:
        (session_dir / "raw_output.md").write_text(result.raw_output_text, encoding="utf-8")

    return _build_local_task_run(
        package=package,
        run=run,
        process_id=process_id,
        lifecycle=lifecycle,
        verifier=verifier,
        agent=_normalized_agent_evidence(
            model=model,
            adapter_kind=adapter_kind,
            execution_mode="persistent_context",
            memory_visibility_policy=visibility_policy.value,
            max_turns=max_turns,
            sessions=_persistent_context_sessions(run),
            lifecycle=lifecycle,
        ),
        sweep_context=sweep_context,
        repository_dir=repository_dir,
        experiment_recorder=experiment_recorder,
    )


def validate_completed_persistent_lifecycle_recovery(
    package_dir: Path,
    run_dir: Path,
) -> dict[str, Any]:
    """Validate durable evidence needed to seal a terminal persistent-session crash."""
    lifecycle = read_evidence_lifecycle_state(Path(package_dir), Path(run_dir))
    if lifecycle["status"] != "complete":
        raise EvidenceLifecycleError("persistent terminal recovery requires complete lifecycle state")
    session_ids = {
        str(attempt["session_id"])
        for checkpoint in lifecycle.get("checkpoint_runs", [])
        for attempt in checkpoint.get("attempts", [])
    }
    if not session_ids:
        raise EvidenceLifecycleError("complete lifecycle has no persistent session lineage")
    for session_id in sorted(session_ids):
        session_dir = Path(run_dir) / "sessions" / session_id
        result_path = session_dir / "agent_result.json"
        trajectory_path = session_dir / "trajectory.jsonl"
        if not session_dir.is_dir() or not trajectory_path.is_file():
            raise EvidenceLifecycleError(f"interrupted session lacks durable trajectory evidence: {session_id}")
        _validate_session_trajectory(trajectory_path, session_id)
        if result_path.is_file():
            try:
                _read_json(result_path)
            except (OSError, ValueError):
                pass
    return lifecycle


def seal_interrupted_persistent_lifecycle_session_results(
    *,
    package_dir: Path,
    run_dir: Path,
    model: str,
    adapter_kind: str,
    max_turns: int,
    visibility_policy: LifecycleVisibilityPolicy,
) -> dict[str, Any]:
    """Seal missing persistent results without invoking an adapter or publishing an experiment."""
    return seal_interrupted_lifecycle_session_results(
        package_dir=package_dir,
        run_dir=run_dir,
        model=model,
        adapter_kind=adapter_kind,
        max_turns=max_turns,
        execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
        visibility_policy=visibility_policy,
    )


def seal_interrupted_lifecycle_session_results(
    *,
    package_dir: Path,
    run_dir: Path,
    model: str,
    adapter_kind: str,
    max_turns: int,
    execution_mode: LifecycleExecutionMode,
    visibility_policy: LifecycleVisibilityPolicy,
) -> dict[str, Any]:
    """Seal missing interrupted session results for one frozen mode without invoking an adapter."""
    lifecycle = read_evidence_lifecycle_state(Path(package_dir), Path(run_dir))
    session_ids = {
        str(attempt["session_id"])
        for checkpoint in lifecycle.get("checkpoint_runs", [])
        for attempt in checkpoint.get("attempts", [])
    }
    if not session_ids:
        raise EvidenceLifecycleError("interrupted lifecycle has no session lineage")
    _seal_interrupted_sessions(
        run=Path(run_dir),
        lifecycle=lifecycle,
        model=model,
        adapter_kind=adapter_kind,
        max_turns=max_turns,
        execution_mode=execution_mode.value,
        memory_visibility_policy=visibility_policy.value,
    )
    return lifecycle


def recover_completed_persistent_lifecycle_session(
    *,
    package_dir: Path,
    run_dir: Path,
    model: str,
    verifier: Any,
    adapter_kind: str,
    max_turns: int,
    process_id: str,
    visibility_policy: LifecycleVisibilityPolicy,
    sweep_context: LifecycleExperimentSweepContext,
    repository_dir: Path,
    experiment_recorder: LifecycleExperimentRecorder | None = None,
) -> dict[str, Any]:
    """Seal a complete persistent crash and publish an unscored canonical invocation."""
    package = Path(package_dir)
    run = Path(run_dir)
    lifecycle = validate_completed_persistent_lifecycle_recovery(package, run)
    _seal_interrupted_sessions(
        run=run,
        lifecycle=lifecycle,
        model=model,
        adapter_kind=adapter_kind,
        max_turns=max_turns,
        execution_mode="persistent_context",
        memory_visibility_policy=visibility_policy.value,
    )
    return _build_local_task_run(
        package=package,
        run=run,
        process_id=process_id,
        lifecycle=lifecycle,
        verifier=verifier,
        agent=_normalized_agent_evidence(
            model=model,
            adapter_kind=adapter_kind,
            execution_mode="persistent_context",
            memory_visibility_policy=visibility_policy.value,
            max_turns=max_turns,
            sessions=_persistent_context_sessions(run),
            lifecycle=lifecycle,
        ),
        sweep_context=sweep_context,
        repository_dir=repository_dir,
        experiment_recorder=experiment_recorder,
    )


def run_local_evidence_lifecycle_fresh_context(
    *,
    package_dir: Path,
    run_dir: Path,
    model: str,
    verifier: Any,
    adapter_kind: str = "tool_loop",
    max_turns: int = 20,
    process_id: str = "process.lifecycle",
    registry: Any | None = None,
    visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
    sweep_context: LifecycleExperimentSweepContext | None = None,
    repository_dir: Path | None = None,
    require_adapter_identity_match: bool = False,
    experiment_recorder: LifecycleExperimentRecorder | None = None,
    run_authorization_sha256: str | None = None,
) -> dict[str, Any]:
    """Run every checkpoint in a fresh adapter and return the normalized local result."""
    package = Path(package_dir)
    run = Path(run_dir)
    if visibility_policy == LifecycleVisibilityPolicy.PERSISTENT_CONTEXT:
        raise ValueError("fresh-context visibility cannot be persistent_context")
    episode_environment = build_local_evidence_lifecycle_episode_environment(
        package_dir=package,
        model=model,
        adapter_kind=adapter_kind,
        max_turns=max_turns,
        registry=registry,
        visibility_policy=visibility_policy,
        require_adapter_identity_match=require_adapter_identity_match,
    )
    try:
        lifecycle = run_evidence_lifecycle(
            package,
            run,
            episode_environment=episode_environment,
            run_authorization_sha256=run_authorization_sha256,
        )
    except LifecycleEpisodeExecutionError:
        lifecycle = read_evidence_lifecycle_state(package, run)
    except Exception:
        lifecycle = read_evidence_lifecycle_state(package, run)
        sessions = _fresh_context_sessions(run)
        _build_local_task_run(
            package=package,
            run=run,
            process_id=process_id,
            lifecycle=lifecycle,
            verifier=verifier,
            agent=_normalized_agent_evidence(
                model=model,
                adapter_kind=adapter_kind,
                execution_mode="fresh_context",
                memory_visibility_policy=visibility_policy.value,
                max_turns=max_turns,
                sessions=sessions,
                lifecycle=lifecycle,
            ),
            sweep_context=sweep_context,
            repository_dir=repository_dir,
            experiment_recorder=experiment_recorder,
        )
        raise
    sessions = _fresh_context_sessions(run)
    return _build_local_task_run(
        package=package,
        run=run,
        process_id=process_id,
        lifecycle=lifecycle,
        verifier=verifier,
        agent=_normalized_agent_evidence(
            model=model,
            adapter_kind=adapter_kind,
            execution_mode="fresh_context",
            memory_visibility_policy=visibility_policy.value,
            max_turns=max_turns,
            sessions=sessions,
            lifecycle=lifecycle,
        ),
        sweep_context=sweep_context,
        repository_dir=repository_dir,
        experiment_recorder=experiment_recorder,
    )


@dataclass(frozen=True)
class LocalEvidenceLifecycleEpisodeEnvironment:
    """Execute fresh checkpoint episodes through one provider-neutral local adapter registry."""

    package_dir: Path
    model: str
    adapter_kind: str = "tool_loop"
    max_turns: int = 20
    registry: Any | None = None
    memory_visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    require_adapter_identity_match: bool = False
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT

    @property
    def requested_adapter(self) -> str:
        return self.adapter_kind

    @property
    def requested_model(self) -> str:
        return self.model

    @property
    def max_turns_per_session(self) -> int:
        return self.max_turns

    def __post_init__(self) -> None:
        if self.memory_visibility_policy is LifecycleVisibilityPolicy.PERSISTENT_CONTEXT:
            raise ValueError("fresh-context visibility cannot be persistent_context")
        if self.execution_mode is not LifecycleExecutionMode.FRESH_CONTEXT:
            raise ValueError("local checkpoint episodes require fresh_context execution")

    def recover(self, context: LifecycleEpisodeContext) -> None:
        """Seal interrupted session evidence before the host allocates a retry attempt."""
        _seal_interrupted_sessions(
            run=Path(context.run_dir),
            lifecycle=context.model_dump(mode="json"),
            model=self.model,
            adapter_kind=self.adapter_kind,
            max_turns=self.max_turns,
            execution_mode=self.execution_mode.value,
            memory_visibility_policy=self.memory_visibility_policy.value,
        )

    def prepare(self, request: LifecycleEpisodeRequest) -> None:
        """Publish a valid empty trajectory before the host records the active attempt."""
        episode_dir = Path(request.run_dir) / "episodes" / request.checkpoint_id / request.session_id
        mkdir_durable(episode_dir)
        trajectory_writer = TrajectoryWriter(path=str(episode_dir / "trajectory.jsonl"))
        trajectory_writer.close()
        fsync_directory(episode_dir)

    def record_failure(
        self,
        request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        """Make the durable local agent result agree with host attempt rejection."""
        result_path = (
            Path(request.run_dir) / "episodes" / request.checkpoint_id / request.session_id / "agent_result.json"
        )
        if result_path.is_file():
            payload = _read_json(result_path)
        else:
            payload = _failed_agent_result(
                model=self.model,
                adapter_kind=self.adapter_kind,
                max_turns=self.max_turns,
                session_id=request.session_id,
                provider_error=provider_error or failure_kind,
                checkpoint_id=request.checkpoint_id,
                memory_visibility_policy=self.memory_visibility_policy.value,
            )
        payload["status"] = "failed"
        payload["failure_kind"] = failure_kind
        if provider_error is not None:
            payload["provider_error"] = provider_error
        _write_json(result_path, payload)

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        """Run one already-allocated host episode and return verifier-independent evidence."""
        checkpoint_id = request.checkpoint_id
        run_dir = Path(request.run_dir)
        episode_dir = run_dir / "episodes" / checkpoint_id / request.session_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        trajectory_path = episode_dir / "trajectory.jsonl"
        trajectory_writer = TrajectoryWriter(path=str(trajectory_path))
        workspace_tool = EvidenceLifecycleWorkspaceTool(
            package_dir=Path(self.package_dir),
            run_dir=run_dir,
            visibility_policy=self.memory_visibility_policy,
        )
        control = EvidenceLifecycleControlTool(
            package_dir=Path(self.package_dir),
            run_dir=run_dir,
            session_id=request.session_id,
        )
        supports_evidence_requests = _supports_evidence_requests(self.package_dir)
        supports_lifecycle_operations = _supports_lifecycle_operations(self.package_dir)
        tools = [
            ToolSpec(name="list_workspace", source="builtin", description="List visible lifecycle files."),
            ToolSpec(name="read_workspace_file", source="builtin", description="Read one visible lifecycle file."),
            ToolSpec(
                name="write_checkpoint_submission",
                source="builtin",
                description="Write the active checkpoint JSON submission.",
            ),
        ]
        native_tools = [
            workspace_tool.list_workspace,
            workspace_tool.read_workspace_file,
            workspace_tool.write_checkpoint_submission,
        ]
        if supports_evidence_requests:
            native_tools.append(control.request_evidence)
            tools.append(
                ToolSpec(
                    name="request_evidence",
                    source="builtin",
                    description="Request one declared evidence packet within the active checkpoint budget.",
                )
            )
        if supports_lifecycle_operations:
            native_tools.append(control.execute_operation)
            tools.append(
                ToolSpec(
                    name="execute_operation",
                    source="builtin",
                    description="Execute one declared operation against the current visible source state.",
                )
            )
        resolved_registry = self.registry or LocalAdapterRegistry()
        try:
            adapter = resolved_registry.build(
                adapter_kind=self.adapter_kind,
                model_name=self.model,
                workspace=request.workspace,
                trajectory_writer=trajectory_writer,
                native_tools=native_tools,
                enable_bash=False,
            )
            adapter_result = adapter.execute(
                AdapterRequest(
                    instruction=request.instruction,
                    system_prompt=_workspace_policy(
                        request.model_dump(mode="json"),
                        persistent=False,
                        visibility_policy=self.memory_visibility_policy,
                        supports_evidence_requests=supports_evidence_requests,
                        supports_lifecycle_operations=supports_lifecycle_operations,
                    ),
                    tools=tools,
                    configuration={"max_turns": self.max_turns},
                    output_path=request.submission_path,
                    output_format="json",
                )
            )
        except Exception as exc:
            _write_json(
                episode_dir / "agent_result.json",
                _failed_agent_result(
                    model=self.model,
                    adapter_kind=self.adapter_kind,
                    max_turns=self.max_turns,
                    session_id=request.session_id,
                    provider_error=str(exc),
                    checkpoint_id=checkpoint_id,
                    memory_visibility_policy=self.memory_visibility_policy.value,
                ),
            )
            raise LifecycleEpisodeEnvironmentFailure("adapter_exception", str(exc)) from exc
        finally:
            trajectory_writer.close()

        if adapter_result.raw_output_text and not Path(request.submission_path).exists():
            (episode_dir / "raw_output.md").write_text(adapter_result.raw_output_text, encoding="utf-8")
        _write_conversation(episode_dir / "conversation.jsonl", adapter_result.transcript)
        adapter_name = str(getattr(adapter_result, "adapter_name", self.adapter_kind))
        resolved_model = str(getattr(adapter_result, "resolved_model", self.model))
        returned_failure = (
            "adapter_identity_mismatch"
            if self.require_adapter_identity_match and adapter_name != self.adapter_kind
            else _adapter_failure_kind(adapter_result)
        )
        episode_result = LifecycleEpisodeResult(
            episode_id=request.episode_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            checkpoint_ids=request.checkpoint_ids,
            execution_mode=request.execution_mode,
            memory_visibility_policy=request.memory_visibility_policy,
            status="failed" if returned_failure is not None else "completed",
            requested_adapter=self.adapter_kind,
            requested_model=self.model,
            max_turns_per_session=self.max_turns,
            adapter=adapter_name,
            resolved_model=resolved_model,
            configuration=cast(
                dict[str, Any],
                getattr(adapter_result, "configuration_record", {"model": self.model}),
            ),
            usage=LifecycleEpisodeUsage(
                input_tokens=adapter_result.usage_input_tokens or 0,
                output_tokens=adapter_result.usage_output_tokens or 0,
                cache_read_tokens=adapter_result.usage_cache_read_tokens or 0,
                cache_write_tokens=adapter_result.usage_cache_write_tokens or 0,
            ),
            failure_kind=returned_failure,
            provider_error=adapter_result.provider_error if returned_failure is not None else None,
        )
        _write_json(
            episode_dir / "agent_result.json",
            _episode_result_agent_payload(
                episode_result,
                checkpoint_id=checkpoint_id,
            ),
        )
        return episode_result


def build_local_evidence_lifecycle_episode_environment(
    *,
    package_dir: Path,
    model: str,
    adapter_kind: str = "tool_loop",
    max_turns: int = 20,
    registry: Any | None = None,
    visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
    require_adapter_identity_match: bool = False,
) -> LifecycleEpisodeEnvironment:
    """Build the typed fresh-checkpoint environment used by the lifecycle host."""
    return LocalEvidenceLifecycleEpisodeEnvironment(
        package_dir=Path(package_dir),
        model=model,
        adapter_kind=adapter_kind,
        max_turns=max_turns,
        registry=registry,
        memory_visibility_policy=visibility_policy,
        require_adapter_identity_match=require_adapter_identity_match,
    )


def _persistent_session_instruction(
    initial: dict[str, Any],
    *,
    supports_evidence_requests: bool,
    supports_lifecycle_operations: bool = False,
) -> str:
    conditional_guidance = ""
    if supports_evidence_requests:
        conditional_guidance = (
            "Before submitting, inspect checkpoints/<checkpoint_id>/evidence-requests.json. You may call "
            "request_evidence when that active checkpoint declares a request catalogue; the remaining budget "
            "is finite.\n"
        )
    if supports_lifecycle_operations:
        conditional_guidance += (
            "Before submitting, check whether checkpoints/<checkpoint_id>/operations.json exists. When it does, "
            "read it with hydraulics/current-source.json. Use execute_operation with the current visible source "
            "hash for declared calculations or source activation; the remaining budget is finite. Read the "
            "returned workspace artifacts before deciding.\n"
        )
    return (
        "This is one staged evidence lifecycle. Complete every checkpoint in this same session.\n\n"
        "For each checkpoint:\n"
        "1. Use list_workspace and read_workspace_file to inspect the active instruction and released evidence.\n"
        f"{conditional_guidance}"
        "2. Call write_checkpoint_submission with the active checkpoint_id and required JSON content.\n"
        "3. Call submit_checkpoint with the active checkpoint_id.\n"
        "4. If the tool releases another checkpoint, read its returned instruction and continue.\n"
        "5. Stop only after submit_checkpoint returns status=complete.\n\n"
        "At a later checkpoint, you may call revisit_checkpoint with a prior checkpoint_id and a reason when you "
        "need to recheck an earlier fact or decision. Revisiting returns the immutable earlier snapshot and does not "
        "rewind the active checkpoint. Record any correction in the current cumulative submission.\n\n"
        "Do not revise an archived prior submission. Preserve stable finding and decision identities unless the "
        "released evidence supports an explicit transition.\n\n"
        f"Active checkpoint: {initial['checkpoint_id']}\n"
        f"Submission path: {initial['submission_path']}\n\n"
        f"{initial['instruction']}"
    )


def _workspace_policy(
    context: dict[str, Any],
    *,
    persistent: bool,
    visibility_policy: LifecycleVisibilityPolicy,
    supports_evidence_requests: bool,
    supports_lifecycle_operations: bool = False,
) -> str:
    if visibility_policy in {
        LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
    }:
        visible_memory = (
            "Read evidence visible under inbox/ and review state under submissions/. Treat submissions for "
            "completed checkpoints as immutable."
        )
    elif visibility_policy == LifecycleVisibilityPolicy.RAW_EVIDENCE_ONLY:
        visible_memory = "Read cumulative released evidence under inbox/. Prior submissions are not model-visible."
    else:
        visible_memory = (
            "Read only the active checkpoint release under inbox/. Prior releases and submissions are not "
            "model-visible."
        )
    policy = (
        f"Use only the confined lifecycle workspace tools. {visible_memory} Do not infer unreleased evidence. "
        "Arbitrary shell execution is unavailable in this lifecycle."
    )
    if context.get("branch") is not None:
        policy += (
            " This is a derived run: the active checkpoint submission path is editable, while branch_origin/ "
            "contains the immutable parent snapshot used for comparison."
        )
    policy += f" Host visibility policy: {visibility_policy.value}."
    if supports_evidence_requests:
        policy += " Declared within-checkpoint evidence is released only by request_evidence."
    if supports_lifecycle_operations:
        policy += (
            " Declared source-bound calculations and source activation run only through execute_operation. "
            "When the active checkpoint provides an operations catalogue, use it with the current hash in "
            "hydraulics/current-source.json. Operation results are evidence, not verification or reward."
        )
    if persistent:
        policy += (
            " Next-checkpoint evidence is released only by submit_checkpoint. Preserve review continuity across "
            "the full session."
        )
        return policy
    return policy + " This is a fresh checkpoint context; reconstruct continuity from the persisted review artifacts."


def _tool_response(result: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "status": result["status"],
        "completed_checkpoints": [item["checkpoint_id"] for item in result.get("completed_checkpoints", [])],
    }
    if result["status"] != "complete":
        payload.update(
            {
                "checkpoint_id": result["checkpoint_id"],
                "title": result["title"],
                "instruction": result["instruction"],
                "submission_path": result["submission_path"],
                "released_files": result["released_files"],
            }
        )
        if result.get("evidence_request_catalog") is not None:
            payload["evidence_request_catalog"] = result["evidence_request_catalog"]
    return payload


def _operation_tool_response(result: dict[str, Any]) -> dict[str, Any]:
    """Select the model-facing result without host-only session or storage fields."""
    artifacts = [
        {
            "path": artifact["workspace_path"],
            "sha256": artifact["sha256"],
        }
        for artifact in result["artifacts"]
        if artifact.get("workspace_path") is not None
    ]
    payload = {
        "status": result["outcome"],
        "action_id": result["action_id"],
        "checkpoint_id": result["checkpoint_id"],
        "operation_id": result["operation_id"],
        "operation_kind": result["operation_kind"],
        "disposition": result["disposition"],
        "visible_source_state_sha256": result["visible_source_state_after_sha256"],
        "input_projection_sha256": result["input_projection_sha256"],
        "prerequisite_action_ids": result["prerequisite_action_ids"],
        "retained_from_action_id": result["retained_from_action_id"],
        "budget_consumed": result["budget_consumed"],
        "remaining_budget": result["budget_after"],
        "artifacts": artifacts,
    }
    if result["rejection"] is not None:
        payload["rejection"] = result["rejection"]
    return payload


def _agent_result(
    result: Any,
    *,
    model: str,
    adapter_kind: str,
    max_turns: int,
    session_id: str | None = None,
    checkpoint_ids: list[str] | None = None,
    memory_visibility_policy: str,
) -> dict[str, Any]:
    return {
        "checkpoint_ids": checkpoint_ids or [],
        "status": _enum_value(result.agent_output.status),
        "model": model,
        "adapter": adapter_kind,
        "adapter_name": getattr(result, "adapter_name", adapter_kind),
        "resolved_model": getattr(result, "resolved_model", model),
        "configuration_record": getattr(result, "configuration_record", {"model": model}),
        "session_mode": "persistent",
        "memory_visibility_policy": memory_visibility_policy,
        "session_id": session_id,
        "max_turns": max_turns,
        "input_tokens": result.usage_input_tokens or 0,
        "output_tokens": result.usage_output_tokens or 0,
        "cache_read_tokens": result.usage_cache_read_tokens or 0,
        "cache_write_tokens": result.usage_cache_write_tokens or 0,
        "failure_kind": _enum_value(result.failure_kind),
        "provider_error": result.provider_error,
    }


def _episode_result_agent_payload(
    result: LifecycleEpisodeResult,
    *,
    checkpoint_id: str,
) -> dict[str, Any]:
    """Preserve the durable agent-result schema consumed by TrialRecord import."""
    return {
        "checkpoint_id": checkpoint_id,
        "checkpoint_ids": list(result.checkpoint_ids),
        "status": result.status,
        "model": result.requested_model,
        "adapter": result.requested_adapter,
        "adapter_name": result.adapter,
        "resolved_model": result.resolved_model,
        "configuration_record": result.configuration,
        "session_mode": "fresh",
        "memory_visibility_policy": result.memory_visibility_policy.value,
        "session_id": result.session_id,
        "max_turns": result.max_turns_per_session,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "cache_read_tokens": result.usage.cache_read_tokens,
        "cache_write_tokens": result.usage.cache_write_tokens,
        "failure_kind": result.failure_kind,
        "provider_error": result.provider_error,
    }


def _failed_agent_result(
    *,
    model: str,
    adapter_kind: str,
    max_turns: int,
    session_id: str,
    provider_error: str,
    checkpoint_id: str | None = None,
    resolved_model: str = "unresolved",
    memory_visibility_policy: str,
) -> dict[str, Any]:
    return {
        "checkpoint_id": checkpoint_id,
        "checkpoint_ids": [checkpoint_id] if checkpoint_id is not None else [],
        "status": "failed",
        "model": model,
        "adapter": adapter_kind,
        "adapter_name": adapter_kind,
        "resolved_model": resolved_model,
        "configuration_record": {"model": model, "max_turns": max_turns},
        "session_mode": "persistent" if checkpoint_id is None else "fresh",
        "memory_visibility_policy": memory_visibility_policy,
        "session_id": session_id,
        "max_turns": max_turns,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "failure_kind": "adapter_exception",
        "provider_error": provider_error,
    }


def _normalized_agent_evidence(
    *,
    model: str,
    adapter_kind: str,
    execution_mode: str,
    memory_visibility_policy: str,
    max_turns: int,
    sessions: list[dict[str, Any]],
    lifecycle: dict[str, Any],
) -> dict[str, Any]:
    sessions = _reconcile_sessions_with_attempts(sessions, lifecycle)
    token_fields = (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    )
    totals = {field: sum(int(session.get(field, 0)) for session in sessions) for field in token_fields}
    totals["failures"] = sum(session.get("status") not in {"completed", "ok"} for session in sessions)
    resolved_adapters = sorted({str(session.get("adapter_name") or "unresolved") for session in sessions})
    return {
        "schema_version": "1",
        "model": model,
        "adapter": adapter_kind,
        "resolved_adapters": resolved_adapters,
        "execution_mode": execution_mode,
        "memory_visibility_policy": memory_visibility_policy,
        "max_turns_per_session": max_turns,
        "status": "failed" if totals["failures"] else "completed",
        "sessions": sessions,
        "totals": totals,
    }


def _reconcile_sessions_with_attempts(
    sessions: list[dict[str, Any]],
    lifecycle: dict[str, Any],
) -> list[dict[str, Any]]:
    """Make host attempt state authoritative when environment artifacts disagree."""
    failed_attempts: dict[str, dict[str, Any]] = {}
    for checkpoint in lifecycle.get("checkpoint_runs", []):
        for attempt in checkpoint.get("attempts", []):
            if attempt.get("status") != "submitted":
                failed_attempts[str(attempt.get("session_id"))] = attempt
    reconciled: list[dict[str, Any]] = []
    for session in sessions:
        payload = dict(session)
        attempt = failed_attempts.get(str(payload.get("session_id")))
        if attempt is not None:
            attempt_status = str(attempt.get("status") or "failed")
            payload["status"] = "failed"
            payload["failure_kind"] = str(attempt.get("failure_kind") or attempt_status)
            if payload.get("provider_error") is None:
                payload["provider_error"] = f"host attempt ended with status {attempt_status}"
        reconciled.append(payload)
    return reconciled


def _adapter_failure_kind(result: Any) -> str | None:
    failure_kind = _enum_value(result.failure_kind)
    if failure_kind is not None:
        return str(failure_kind)
    status = _enum_value(result.agent_output.status)
    return "agent_failed" if status in {"failed", "empty"} else None


def _build_local_task_run(
    *,
    package: Path,
    run: Path,
    process_id: str,
    lifecycle: dict[str, Any],
    verifier: Any,
    agent: dict[str, Any],
    sweep_context: LifecycleExperimentSweepContext | None = None,
    repository_dir: Path | None = None,
    experiment_recorder: LifecycleExperimentRecorder | None = None,
) -> dict[str, Any]:
    spec = load_evidence_lifecycle_spec(package)
    verifier_exception: Exception | None = None
    if lifecycle["status"] == "complete" and agent["status"] == "completed":
        try:
            verification = validate_lifecycle_verification(verifier(package, run))
        except Exception as exc:
            verifier_exception = exc
            verification = validate_lifecycle_verification(
                {
                    "lifecycle_id": spec.lifecycle_id,
                    "overall": "incomplete",
                    "passed": False,
                    "reward": 0.0,
                    "gates": {
                        "lifecycle_verifier": {
                            "passed": False,
                            "score": 0.0,
                            "failures": [f"verifier_exception:{type(exc).__name__}:{exc}"],
                        }
                    },
                }
            )
    else:
        verification = validate_lifecycle_verification(
            {
                "lifecycle_id": spec.lifecycle_id,
                "overall": "incomplete",
                "passed": False,
                "reward": 0.0,
                "gates": {
                    "lifecycle_runtime": {
                        "passed": False,
                        "score": 0.0,
                        "failures": [f"stopped_at:{lifecycle.get('active_checkpoint_id') or lifecycle['status']}"],
                    }
                },
            }
        )
    reward = float(verification["reward"])
    passed = bool(verification["passed"])
    recorder = experiment_recorder if experiment_recorder is not None else record_lifecycle_experiment
    experiment = recorder(
        package_dir=package,
        run_dir=run,
        agent=agent,
        verifier=verifier,
        verification=verification,
        tool_schema=_lifecycle_tool_schema(
            agent["execution_mode"],
            supports_evidence_requests=_supports_evidence_requests(package),
            supports_lifecycle_operations=_supports_lifecycle_operations(package),
        ),
        sweep_context=sweep_context,
        repository_dir=repository_dir,
    )
    if verifier_exception is not None:
        raise verifier_exception
    trajectories = sorted(str(path) for path in run.glob("**/trajectory.jsonl"))
    conversations = sorted(str(path) for path in run.glob("**/conversation.jsonl"))
    return {
        "run_id": f"{process_id}.{spec.lifecycle_id}",
        "evidence": {
            "score": {"reward": reward, "passed": passed},
            "gates": verification.get("gates", {}),
            "lifecycle": lifecycle,
            "verification": verification,
            "agent": agent,
            "experiment": experiment,
            "execution_security": {
                "filesystem_boundary": "workspace_confined_native_tools",
                "arbitrary_shell": False,
            },
            "artifacts": {
                "run_dir": str(run),
                "ledger": str(run / "lifecycle_ledger.jsonl"),
                "trajectories": trajectories,
                "conversations": conversations,
                "verification": experiment["verification"],
                "metrics": experiment["metrics"],
                "manifest": experiment["manifest"],
                "experiment_index": experiment["index"],
            },
        },
    }


def _fresh_context_sessions(run_dir: Path) -> list[dict[str, Any]]:
    return [_read_json(path) for path in sorted(Path(run_dir).glob("episodes/**/agent_result.json"))]


def _persistent_context_sessions(run_dir: Path) -> list[dict[str, Any]]:
    return [_read_json(path) for path in sorted(Path(run_dir).glob("sessions/*/agent_result.json"))]


def _seal_interrupted_sessions(
    *,
    run: Path,
    lifecycle: dict[str, Any],
    model: str,
    adapter_kind: str,
    max_turns: int,
    execution_mode: str,
    memory_visibility_policy: str,
) -> None:
    checkpoint_runs = lifecycle.get("checkpoint_runs", [])
    attempts_by_session: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for checkpoint in checkpoint_runs:
        checkpoint_id = str(checkpoint["checkpoint_id"])
        for attempt in checkpoint.get("attempts", []):
            if attempt.get("inherited_from_parent"):
                continue
            session_id = str(attempt["session_id"])
            attempts_by_session.setdefault(session_id, []).append((checkpoint_id, attempt))
    for session_id, session_attempts in attempts_by_session.items():
        first_checkpoint = session_attempts[0][0]
        if execution_mode == "persistent_context":
            session_dir = run / "sessions" / session_id
            checkpoint_value = None
        else:
            session_dir = run / "episodes" / first_checkpoint / session_id
            checkpoint_value = first_checkpoint
        result_path = session_dir / "agent_result.json"
        has_active_attempt = any(attempt.get("status") == "active" for _, attempt in session_attempts)
        terminal_crash = lifecycle.get("status") == "complete" and all(
            attempt.get("status") == "submitted" for _, attempt in session_attempts
        )
        if result_path.is_file() and not has_active_attempt:
            try:
                _read_json(result_path)
            except (OSError, ValueError) as exc:
                if not terminal_crash:
                    raise EvidenceLifecycleError(f"interrupted session result is malformed: {session_id}") from exc
                corrupt_path = session_dir / "agent_result.corrupt.json"
                if corrupt_path.exists():
                    raise EvidenceLifecycleError(
                        f"terminal session already has quarantined result: {session_id}"
                    ) from exc
                result_path.replace(corrupt_path)
                fsync_directory(session_dir)
            else:
                continue
        trajectory_path = session_dir / "trajectory.jsonl"
        if not session_dir.is_dir() or not trajectory_path.is_file():
            raise EvidenceLifecycleError(f"interrupted session lacks durable trajectory evidence: {session_id}")
        _validate_session_trajectory(trajectory_path, session_id)
        if result_path.is_file():
            payload = _read_json(result_path)
        else:
            payload = _failed_agent_result(
                model=model,
                adapter_kind=adapter_kind,
                max_turns=max_turns,
                session_id=session_id,
                provider_error="session interrupted before a durable agent result was recorded",
                checkpoint_id=checkpoint_value,
                memory_visibility_policy=memory_visibility_policy,
            )
            payload["adapter_name"] = "unresolved"
        payload["status"] = "failed"
        payload["failure_kind"] = "interrupted_after_completion" if terminal_crash else "interrupted"
        payload["checkpoint_ids"] = _session_checkpoint_ids(lifecycle, session_id)
        if payload.get("provider_error") is None:
            payload["provider_error"] = (
                "session interrupted after lifecycle completion"
                if terminal_crash
                else "session interrupted before lifecycle completion"
            )
        _write_json(result_path, payload)


def _session_checkpoint_ids(lifecycle: dict[str, Any], session_id: str) -> list[str]:
    checkpoint_ids: list[str] = []
    for checkpoint in lifecycle.get("checkpoint_runs", []):
        if any(attempt.get("session_id") == session_id for attempt in checkpoint.get("attempts", [])):
            checkpoint_ids.append(str(checkpoint["checkpoint_id"]))
    return checkpoint_ids


def _supports_evidence_requests(package_dir: Path) -> bool:
    spec = load_evidence_lifecycle_spec(Path(package_dir))
    return any(checkpoint.conditional_evidence is not None for checkpoint in spec.checkpoints)


def _supports_lifecycle_operations(package_dir: Path) -> bool:
    spec = load_evidence_lifecycle_spec(Path(package_dir))
    return any(checkpoint.conditional_operations is not None for checkpoint in spec.checkpoints)


def build_lifecycle_tool_schema(
    execution_mode: str,
    *,
    supports_evidence_requests: bool,
    supports_lifecycle_operations: bool = False,
) -> list[dict[str, str]]:
    """Build the exact host tool schema bound into lifecycle execution provenance."""
    return _lifecycle_tool_schema(
        execution_mode,
        supports_evidence_requests=supports_evidence_requests,
        supports_lifecycle_operations=supports_lifecycle_operations,
    )


def _lifecycle_tool_schema(
    execution_mode: str,
    *,
    supports_evidence_requests: bool,
    supports_lifecycle_operations: bool = False,
) -> list[dict[str, str]]:
    functions: list[Callable[..., Any]] = [
        EvidenceLifecycleWorkspaceTool.list_workspace,
        EvidenceLifecycleWorkspaceTool.read_workspace_file,
        EvidenceLifecycleWorkspaceTool.write_checkpoint_submission,
    ]
    if supports_evidence_requests:
        functions.append(EvidenceLifecycleControlTool.request_evidence)
    if supports_lifecycle_operations:
        functions.append(EvidenceLifecycleControlTool.execute_operation)
    if execution_mode == "persistent_context":
        functions.extend(
            [
                EvidenceLifecycleControlTool.submit_checkpoint,
                EvidenceLifecycleControlTool.revisit_checkpoint,
            ]
        )
    return [
        {
            "name": function.__name__,
            "signature": str(
                inspect.signature(function).replace(
                    parameters=[
                        parameter
                        for name, parameter in inspect.signature(function).parameters.items()
                        if name != "self"
                    ]
                )
            ),
            "description": inspect.getdoc(function) or "",
        }
        for function in functions
    ]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EvidenceLifecycleError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _validate_session_trajectory(path: Path, session_id: str) -> None:
    try:
        read_trajectory(path)
    except (OSError, ValueError) as exc:
        raise EvidenceLifecycleError(f"session trajectory is malformed: {session_id}") from exc


def _next_session_id(run_dir: Path) -> str:
    sessions_dir = run_dir / "sessions"
    sequences = []
    for path in sessions_dir.glob("session-*"):
        if not path.is_dir():
            continue
        try:
            sequences.append(int(path.name.removeprefix("session-")))
        except ValueError:
            continue
    return f"session-{max(sequences, default=0) + 1:03d}"


def _write_conversation(path: Path, transcript: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in transcript:
            handle.write(
                json.dumps(
                    {
                        "role": _enum_value(entry.role),
                        "event": _enum_value(entry.event),
                        "content": entry.content or "",
                        "tool_name": entry.tool_name,
                        "tool_call_id": entry.tool_call_id,
                    }
                )
                + "\n"
            )


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    mkdir_durable(path.parent)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
