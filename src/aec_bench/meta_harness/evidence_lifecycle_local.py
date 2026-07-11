# ABOUTME: Runs evidence lifecycles through persistent or fresh local agent sessions.
# ABOUTME: Preserves checkpoint attempts, revisits, trajectories, usage, and provider outcomes.

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, cast

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.local_registry import LocalAdapterRegistry
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    fail_checkpoint_attempt,
    load_evidence_lifecycle_spec,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
    revisit_evidence_checkpoint,
    run_evidence_lifecycle,
    submit_evidence_checkpoint,
    validate_lifecycle_verification,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import record_lifecycle_experiment
from aec_bench.trajectory.writer import TrajectoryWriter


class _LocalAdapterExecutionFailure(EvidenceLifecycleError):
    """Stop fresh-context progression after a returned adapter failure."""


class LifecycleVisibilityPolicy(StrEnum):
    """Host-controlled model visibility over the durable lifecycle workspace."""

    PERSISTENT_CONTEXT = "persistent_context"
    ARTIFACT_MEMORY = "artifact_memory"
    RAW_EVIDENCE_ONLY = "raw_evidence_only"
    CURRENT_RELEASE_ONLY = "current_release_only"


@dataclass(frozen=True)
class EvidenceLifecycleControlTool:
    """Host-controlled checkpoint transition exposed to one persistent agent."""

    package_dir: Path
    run_dir: Path
    session_id: str = "manual"

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
            if payload.get("checkpoint_id") != checkpoint_id:
                raise EvidenceLifecycleError(f"checkpoint submission id must be {checkpoint_id!r}")
            spec = load_evidence_lifecycle_spec(self.package_dir)
            checkpoint = next(item for item in spec.checkpoints if item.checkpoint_id == checkpoint_id)
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
) -> dict[str, Any]:
    """Run all checkpoints in one adapter execution and one model conversation."""
    if adapter_kind not in {"tool_loop", "pydantic_ai"}:
        raise ValueError("persistent evidence lifecycles require a native tool-loop adapter")
    if visibility_policy != LifecycleVisibilityPolicy.PERSISTENT_CONTEXT:
        raise ValueError("persistent sessions require persistent_context visibility")

    package = Path(package_dir)
    run = Path(run_dir)
    initial = prepare_evidence_checkpoint(package, run)
    if initial["status"] == "complete":
        raise EvidenceLifecycleError("lifecycle run is already complete")

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
    resolved_registry = registry or LocalAdapterRegistry()
    try:
        adapter = resolved_registry.build(
            adapter_kind=adapter_kind,
            model_name=model,
            workspace=initial["workspace"],
            trajectory_writer=trajectory_writer,
            native_tools=[
                workspace_tool.list_workspace,
                workspace_tool.read_workspace_file,
                workspace_tool.write_checkpoint_submission,
                control.submit_checkpoint,
                control.revisit_checkpoint,
            ],
            enable_bash=False,
        )
        result = adapter.execute(
            AdapterRequest(
                instruction=_persistent_session_instruction(initial),
                system_prompt=_workspace_policy(
                    initial,
                    persistent=True,
                    visibility_policy=visibility_policy,
                ),
                tools=[
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
                ],
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
        )
        _write_json(session_dir / "agent_result.json", failed_agent_result)
        lifecycle = read_evidence_lifecycle_state(package, run)
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
                sessions=[failed_agent_result],
            ),
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
    )
    returned_failure = _adapter_failure_kind(result)
    if returned_failure is not None:
        fail_checkpoint_attempt(
            package,
            run,
            session_id=session_id,
            failure_kind=returned_failure,
        )
    lifecycle = read_evidence_lifecycle_state(package, run)
    agent_result["checkpoint_ids"] = [item["checkpoint_id"] for item in lifecycle["completed_checkpoints"]]
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
            sessions=[agent_result],
        ),
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
) -> dict[str, Any]:
    """Run every checkpoint in a fresh adapter and return the normalized local result."""
    package = Path(package_dir)
    run = Path(run_dir)
    if visibility_policy == LifecycleVisibilityPolicy.PERSISTENT_CONTEXT:
        raise ValueError("fresh-context visibility cannot be persistent_context")
    episode_resolver = build_local_evidence_lifecycle_episode_resolver(
        package_dir=package,
        model=model,
        adapter_kind=adapter_kind,
        max_turns=max_turns,
        registry=registry,
        visibility_policy=visibility_policy,
    )
    try:
        lifecycle = run_evidence_lifecycle(package, run, episode_resolver=episode_resolver)
    except _LocalAdapterExecutionFailure:
        lifecycle = read_evidence_lifecycle_state(package, run)
    except Exception:
        lifecycle = read_evidence_lifecycle_state(package, run)
        spec = load_evidence_lifecycle_spec(package)
        sessions = [
            _read_json(run / "episodes" / checkpoint.checkpoint_id / "agent_result.json")
            for checkpoint in spec.checkpoints
            if (run / "episodes" / checkpoint.checkpoint_id / "agent_result.json").is_file()
        ]
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
            ),
        )
        raise
    spec = load_evidence_lifecycle_spec(package)
    sessions = [
        _read_json(run / "episodes" / checkpoint.checkpoint_id / "agent_result.json")
        for checkpoint in spec.checkpoints
        if (run / "episodes" / checkpoint.checkpoint_id / "agent_result.json").is_file()
    ]
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
        ),
    )


def build_local_evidence_lifecycle_episode_resolver(
    *,
    package_dir: Path,
    model: str,
    adapter_kind: str = "tool_loop",
    max_turns: int = 20,
    registry: Any | None = None,
    visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
) -> Any:
    """Build a resolver that creates a fresh adapter for every checkpoint."""
    if visibility_policy == LifecycleVisibilityPolicy.PERSISTENT_CONTEXT:
        raise ValueError("fresh-context visibility cannot be persistent_context")
    resolved_registry = registry or LocalAdapterRegistry()

    def resolve(context: dict[str, Any]) -> dict[str, Any]:
        checkpoint_id = str(context["checkpoint_id"])
        workspace = str(context["workspace"])
        checkpoint_run = next(item for item in context["checkpoint_runs"] if item["checkpoint_id"] == checkpoint_id)
        session_id = f"{checkpoint_id}.session-{len(checkpoint_run['attempts']) + 1:03d}"
        episode_dir = Path(context["run_dir"]) / "episodes" / checkpoint_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        trajectory_path = episode_dir / "trajectory.jsonl"
        trajectory_writer = TrajectoryWriter(path=str(trajectory_path))
        open_checkpoint_attempt(
            Path(package_dir),
            Path(context["run_dir"]),
            session_id=session_id,
            execution_mode="fresh_context",
        )
        workspace_tool = EvidenceLifecycleWorkspaceTool(
            package_dir=Path(package_dir),
            run_dir=Path(context["run_dir"]),
            visibility_policy=visibility_policy,
        )
        tools = [
            ToolSpec(name="list_workspace", source="builtin", description="List visible lifecycle files."),
            ToolSpec(name="read_workspace_file", source="builtin", description="Read one visible lifecycle file."),
            ToolSpec(
                name="write_checkpoint_submission",
                source="builtin",
                description="Write the active checkpoint JSON submission.",
            ),
        ]
        try:
            adapter = resolved_registry.build(
                adapter_kind=adapter_kind,
                model_name=model,
                workspace=workspace,
                trajectory_writer=trajectory_writer,
                native_tools=[
                    workspace_tool.list_workspace,
                    workspace_tool.read_workspace_file,
                    workspace_tool.write_checkpoint_submission,
                ],
                enable_bash=False,
            )
            result = adapter.execute(
                AdapterRequest(
                    instruction=str(context["instruction"]),
                    system_prompt=_workspace_policy(
                        context,
                        persistent=False,
                        visibility_policy=visibility_policy,
                    ),
                    tools=tools,
                    configuration={"max_turns": max_turns},
                    output_path=str(context["submission_path"]),
                    output_format="json",
                )
            )
        except Exception as exc:
            fail_checkpoint_attempt(
                Path(package_dir),
                Path(context["run_dir"]),
                session_id=session_id,
                failure_kind="adapter_exception",
            )
            _write_json(
                episode_dir / "agent_result.json",
                _failed_agent_result(
                    model=model,
                    adapter_kind=adapter_kind,
                    max_turns=max_turns,
                    session_id=session_id,
                    provider_error=str(exc),
                    checkpoint_id=checkpoint_id,
                ),
            )
            raise
        finally:
            trajectory_writer.close()
        if result.raw_output_text and not Path(context["submission_path"]).exists():
            (episode_dir / "raw_output.md").write_text(result.raw_output_text, encoding="utf-8")

        agent_result = {
            "checkpoint_id": checkpoint_id,
            "checkpoint_ids": [checkpoint_id],
            "status": result.agent_output.status.value,
            "model": model,
            "adapter": adapter_kind,
            "adapter_name": getattr(result, "adapter_name", adapter_kind),
            "resolved_model": getattr(result, "resolved_model", model),
            "configuration_record": getattr(result, "configuration_record", {"model": model}),
            "session_mode": "fresh",
            "session_id": session_id,
            "max_turns": max_turns,
            "input_tokens": result.usage_input_tokens or 0,
            "output_tokens": result.usage_output_tokens or 0,
            "cache_read_tokens": result.usage_cache_read_tokens or 0,
            "cache_write_tokens": result.usage_cache_write_tokens or 0,
            "failure_kind": _enum_value(result.failure_kind),
            "provider_error": result.provider_error,
        }
        _write_json(episode_dir / "agent_result.json", agent_result)
        _write_conversation(episode_dir / "conversation.jsonl", result.transcript)
        returned_failure = _adapter_failure_kind(result)
        if returned_failure is not None:
            fail_checkpoint_attempt(
                Path(package_dir),
                Path(context["run_dir"]),
                session_id=session_id,
                failure_kind=returned_failure,
            )
            raise _LocalAdapterExecutionFailure(f"adapter failed at checkpoint {checkpoint_id}: {returned_failure}")
        return agent_result

    return resolve


def _persistent_session_instruction(initial: dict[str, Any]) -> str:
    return (
        "This is one staged evidence lifecycle. Complete every checkpoint in this same session.\n\n"
        "For each checkpoint:\n"
        "1. Use list_workspace and read_workspace_file to inspect the active instruction and released evidence.\n"
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
    if persistent:
        return (
            policy
            + " Future evidence is released only by the submit_checkpoint tool. Preserve review continuity across "
            "the full session."
        )
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
    return payload


def _agent_result(
    result: Any,
    *,
    model: str,
    adapter_kind: str,
    max_turns: int,
    session_id: str | None = None,
    checkpoint_ids: list[str] | None = None,
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
        "session_id": session_id,
        "max_turns": max_turns,
        "input_tokens": result.usage_input_tokens or 0,
        "output_tokens": result.usage_output_tokens or 0,
        "cache_read_tokens": result.usage_cache_read_tokens or 0,
        "cache_write_tokens": result.usage_cache_write_tokens or 0,
        "failure_kind": _enum_value(result.failure_kind),
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
) -> dict[str, Any]:
    return {
        "checkpoint_id": checkpoint_id,
        "checkpoint_ids": [checkpoint_id] if checkpoint_id is not None else [],
        "status": "failed",
        "model": model,
        "adapter": adapter_kind,
        "adapter_name": adapter_kind,
        "resolved_model": model,
        "configuration_record": {"model": model, "max_turns": max_turns},
        "session_mode": "persistent" if checkpoint_id is None else "fresh",
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
) -> dict[str, Any]:
    token_fields = (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    )
    totals = {field: sum(int(session.get(field, 0)) for session in sessions) for field in token_fields}
    totals["failures"] = sum(session.get("status") == "failed" for session in sessions)
    return {
        "schema_version": "1",
        "model": model,
        "adapter": adapter_kind,
        "execution_mode": execution_mode,
        "memory_visibility_policy": memory_visibility_policy,
        "max_turns_per_session": max_turns,
        "status": "failed" if totals["failures"] else "completed",
        "sessions": sessions,
        "totals": totals,
    }


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
) -> dict[str, Any]:
    spec = load_evidence_lifecycle_spec(package)
    verifier_exception: Exception | None = None
    if lifecycle["status"] == "complete":
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
    experiment = record_lifecycle_experiment(
        package_dir=package,
        run_dir=run,
        agent=agent,
        verifier=verifier,
        verification=verification,
        tool_schema=_lifecycle_tool_schema(agent["execution_mode"]),
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


def _lifecycle_tool_schema(execution_mode: str) -> list[dict[str, str]]:
    functions: list[Callable[..., Any]] = [
        EvidenceLifecycleWorkspaceTool.list_workspace,
        EvidenceLifecycleWorkspaceTool.read_workspace_file,
        EvidenceLifecycleWorkspaceTool.write_checkpoint_submission,
    ]
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
            "signature": str(inspect.signature(function)),
            "description": inspect.getdoc(function) or "",
        }
        for function in functions
    ]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EvidenceLifecycleError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
