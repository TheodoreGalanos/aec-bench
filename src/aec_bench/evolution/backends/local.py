# ABOUTME: Local solve backend for the evolution orchestrator.
# ABOUTME: Handles snapshot injection, artifact collection, and task execution.

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.evolution import WorkspaceSnapshot
from aec_bench.contracts.trial_record import (
    AgentReference,
    Completeness,
    CostRecord,
    EnvironmentSnapshot,
    InputRecord,
    OutputRecord,
    TaskReference,
    TimingRecord,
    TrialRecord,
)
from aec_bench.evolution.snapshot import serialise_snapshot

_log = logging.getLogger(__name__)

# Type alias for the callable signature expected by EvolutionOrchestrator.
SolveFn = Callable[[WorkspaceSnapshot, int], list[TrialRecord]]


def make_stub_solve_fn(records: list[TrialRecord]) -> SolveFn:
    """Create a solve function that returns the same records every cycle.

    Intended for testing and as a placeholder until a real local backend is
    available. Returns at most batch_size records per call.
    """

    def solve(snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
        return records[:batch_size]

    return solve


def inject_snapshot_into_workspace(snapshot: WorkspaceSnapshot, workspace_dir: Path) -> None:
    """Write the serialised workspace snapshot as system_prompt.md.

    Overwrites any existing file at that path. The agent reads this file to
    obtain its system prompt and domain knowledge skills at runtime.
    """
    content = serialise_snapshot(snapshot)
    (workspace_dir / "system_prompt.md").write_text(content)
    _log.debug("Injected snapshot (version=%s) into %s", snapshot.workspace_version, workspace_dir)


_ADAPTER_CONFIG_FILES: tuple[str, ...] = ("tool_loop.toml",)


def copy_adapter_config(workspace_root: Path, trial_workspace: Path) -> None:
    """Copy adapter-level config files (e.g. tool_loop.toml) into a per-trial workspace.

    Local adapter builders read these files from the trial workspace to wire
    advisor clients, tool settings, and similar concerns. Silently skips any
    files that are not present at the workspace root.
    """
    for filename in _ADAPTER_CONFIG_FILES:
        source = workspace_root / filename
        if source.is_file():
            shutil.copy2(source, trial_workspace / filename)


def collect_local_trial_record(
    *,
    workspace_dir: Path,
    trial_id: str,
    experiment_id: str,
    task_id: str,
    model: str,
    instruction: str,
    adapter: str = "rlm",
) -> TrialRecord:
    """Build a TrialRecord from local run artifacts in workspace_dir.

    Reads agent_result.json, verifier outputs, and optional conversation and
    trajectory files. Missing verifier artifacts are handled gracefully by
    setting reward=0.0 and verifier_completed=False.
    """
    # --- agent_result.json ---------------------------------------------------
    agent_result_path = workspace_dir / "agent_result.json"
    agent_result: dict | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cache_read: int | None = None
    cache_write: int | None = None
    advisor_calls: int | None = None
    advisor_input_tokens: int | None = None
    advisor_output_tokens: int | None = None

    if agent_result_path.exists():
        agent_result = json.loads(agent_result_path.read_text())
        tokens_in = agent_result.get("input_tokens")
        tokens_out = agent_result.get("output_tokens")
        cache_read = agent_result.get("cache_read_tokens")
        cache_write = agent_result.get("cache_write_tokens")
        advisor_calls = agent_result.get("advisor_calls")
        advisor_input_tokens = agent_result.get("advisor_input_tokens")
        advisor_output_tokens = agent_result.get("advisor_output_tokens")

    # --- verifier outputs ----------------------------------------------------
    reward_path = workspace_dir / "logs" / "verifier" / "reward.json"
    details_path = workspace_dir / "logs" / "verifier" / "details.json"

    verifier_completed = reward_path.exists()
    reward = 0.0
    breakdown: dict | None = None

    if verifier_completed:
        reward_data = json.loads(reward_path.read_text())
        reward = float(reward_data["reward"])
        if details_path.exists():
            breakdown = json.loads(details_path.read_text())

    validity = ValidityCheck(
        output_parseable=True,
        schema_valid=True,
        verifier_completed=verifier_completed,
    )
    evaluation = EvaluationResult(reward=reward, validity=validity, breakdown=breakdown)

    # --- optional artifact paths ---------------------------------------------
    conversation_path_val: str | None = None
    conversation_file = workspace_dir / "conversation.jsonl"
    if conversation_file.exists():
        conversation_path_val = str(conversation_file)

    trajectory_path_val: str | None = None
    trajectory_file = workspace_dir / "trajectory.jsonl"
    if trajectory_file.exists():
        trajectory_path_val = str(trajectory_file)

    # --- system prompt provenance --------------------------------------------
    system_prompt_file = workspace_dir / "system_prompt.md"
    system_prompt: str | None = None
    if system_prompt_file.exists():
        system_prompt = system_prompt_file.read_text()

    # --- cost record ---------------------------------------------------------
    cost: CostRecord | None = None
    has_advisor_stats = (
        advisor_calls is not None or advisor_input_tokens is not None or advisor_output_tokens is not None
    )
    if tokens_in is not None or tokens_out is not None or has_advisor_stats:
        cost = CostRecord(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cache_read_tokens=cache_read if cache_read else None,
            cache_write_tokens=cache_write if cache_write else None,
            advisor_calls=advisor_calls,
            advisor_input_tokens=advisor_input_tokens,
            advisor_output_tokens=advisor_output_tokens,
        )

    return TrialRecord(
        trial_id=trial_id,
        experiment_id=experiment_id,
        timestamp=datetime.now(tz=UTC),
        task=TaskReference(task_id=task_id, task_revision="local"),
        agent=AgentReference(adapter=adapter, model=model),
        environment=EnvironmentSnapshot(runtime_image="local", compute_backend="local"),
        inputs=InputRecord(instruction=instruction, system_prompt=system_prompt),
        outputs=OutputRecord(
            conversation_path=conversation_path_val,
            trajectory_path=trajectory_path_val,
            agent_result=agent_result,
        ),
        evaluation=evaluation,
        timing=TimingRecord(total_seconds=0.0),
        cost=cost,
        completeness=Completeness.PARTIAL,
    )


def _extract_task_id(task_dir: Path) -> str:
    """Derive a slash-separated task ID from a task directory path.

    Looks for a "tasks" component in the resolved path and returns everything
    after it. Falls back to the last three path components when "tasks" is not
    present.
    """
    parts = task_dir.resolve().parts
    try:
        tasks_idx = parts.index("tasks")
        return "/".join(parts[tasks_idx + 1 :])
    except ValueError:
        return "/".join(parts[-3:]) if len(parts) >= 3 else task_dir.name


def _select_task_batch(
    task_dirs: list[Path],
    *,
    batch_size: int,
    start_index: int,
) -> list[Path]:
    """Select a rotating batch of task directories from the full suite."""
    if not task_dirs:
        return []
    count = min(batch_size, len(task_dirs))
    return [task_dirs[(start_index + offset) % len(task_dirs)] for offset in range(count)]


class LocalSolver:
    """Solve function object that defers temp workspace cleanup.

    Trial records store absolute paths to artifacts in temporary workspaces.
    The evolution engine needs those files to exist when it classifies traces
    after the solve step. Call ``cleanup()`` once the engine is done with a
    cycle's trial records to remove the temporary directories.
    """

    def __init__(
        self,
        *,
        task_dirs: list[Path],
        model: str,
        experiment_id: str,
        adapter: str = "rlm",
        timeout: int = 1800,
        workspace_root: Path | None = None,
    ) -> None:
        self._task_dirs = task_dirs
        self._model = model
        self._experiment_id = experiment_id
        self._adapter = adapter
        self._timeout = timeout
        self._workspace_root = workspace_root
        self._call_count = 0
        self._task_cursor = 0
        self._pending_workspaces: list[str] = []

    def __call__(self, snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
        """Run tasks and return trial records. Temp dirs are kept until cleanup()."""
        if not self._task_dirs:
            return []

        # Deferred imports — keeps the module importable without pydantic-ai
        from aec_bench.harness.local_runtime import setup_workspace

        records: list[TrialRecord] = []
        selected_task_dirs = _select_task_batch(
            self._task_dirs,
            batch_size=batch_size,
            start_index=self._task_cursor,
        )
        self._task_cursor = (self._task_cursor + len(selected_task_dirs)) % len(self._task_dirs)

        for i, task_dir in enumerate(selected_task_dirs):
            trial_id = f"evo-{self._experiment_id}-c{self._call_count}-t{i}"
            self._call_count += 1

            task_id = _extract_task_id(task_dir)
            instruction_file = task_dir / "instruction.md"
            instruction = instruction_file.read_text() if instruction_file.exists() else ""

            workspace: str | None = None
            try:
                # 1. Setup workspace — copies task files to a temp directory.
                workspace = setup_workspace(str(task_dir))
                workspace_path = Path(workspace)

                # 2. Inject evolved prompt and skills.
                inject_snapshot_into_workspace(snapshot, workspace_path)

                # 2b. Propagate adapter-level config (tool_loop.toml, etc.) from workspace root.
                if self._workspace_root is not None:
                    copy_adapter_config(self._workspace_root, workspace_path)

                # 3. Patch /workspace/ paths in copied files for local execution.
                # Must happen BEFORE the adapter runs so tool paths resolve.
                from aec_bench.harness.local_runtime import patch_workspace_paths

                patch_workspace_paths(workspace)

                # 4. Run adapter in-process via the local adapter registry.
                _run_adapter_in_workspace(
                    adapter_kind=self._adapter,
                    workspace=workspace,
                    model=self._model,
                )

                # 5. Run verifier if it exists.
                verifier = workspace_path / "tests" / "verify.py"
                if verifier.exists():
                    verify_env = dict(os.environ)
                    verify_env["PYTHONPATH"] = workspace
                    output_file = workspace_path / "output.md"
                    reward_file = workspace_path / "logs" / "verifier" / "reward.json"
                    subprocess.run(
                        [
                            sys.executable,
                            str(verifier),
                            "--input",
                            str(output_file),
                            "--output",
                            str(reward_file),
                        ],
                        cwd=workspace,
                        env=verify_env,
                        timeout=120,
                        capture_output=True,
                    )

                # 6. Collect TrialRecord from workspace artifacts.
                record = collect_local_trial_record(
                    workspace_dir=workspace_path,
                    trial_id=trial_id,
                    experiment_id=self._experiment_id,
                    task_id=task_id,
                    model=self._model,
                    instruction=instruction,
                    adapter=self._adapter,
                )
                records.append(record)

                # Track for deferred cleanup — artifacts must survive until
                # the engine finishes classifying this cycle's traces.
                self._pending_workspaces.append(workspace)
                workspace = None  # prevent cleanup in except/finally

            except subprocess.TimeoutExpired:
                _log.warning("Task %s timed out after %ss", task_id, self._timeout)
            except Exception:
                _log.exception("Task %s failed with an unexpected error", task_id)
            finally:
                # Only clean up on failure — successful workspaces are deferred
                if workspace is not None:
                    shutil.rmtree(workspace, ignore_errors=True)

        return records

    def cleanup(self) -> None:
        """Remove all temporary workspaces from completed cycles."""
        for ws in self._pending_workspaces:
            shutil.rmtree(ws, ignore_errors=True)
        self._pending_workspaces.clear()


def make_local_solve_fn(
    *,
    task_dirs: list[Path],
    model: str,
    experiment_id: str,
    adapter: str = "rlm",
    timeout: int = 1800,
    workspace_root: Path | None = None,
) -> LocalSolver:
    """Create a solve function that runs tasks locally via the adapter registry.

    Returns a ``LocalSolver`` callable. After the evolution run completes, call
    ``solver.cleanup()`` to remove temporary workspace directories.

    When ``workspace_root`` is provided, adapter-level config files like
    ``tool_loop.toml`` are copied from that directory into each per-trial
    workspace so local adapter builders can read them.
    """
    return LocalSolver(
        task_dirs=task_dirs,
        model=model,
        experiment_id=experiment_id,
        adapter=adapter,
        timeout=timeout,
        workspace_root=workspace_root,
    )


def _run_adapter_in_workspace(
    *,
    adapter_kind: str,
    workspace: str,
    model: str,
) -> None:
    """Execute a task using the local adapter registry.

    Mirrors the logic from run_local.py's _run_adapter but without CLI
    dependencies. Writes agent_result.json, conversation.jsonl, and
    trajectory.jsonl to the workspace.
    """
    from aec_bench.adapters.base import AdapterRequest
    from aec_bench.adapters.local_registry import LocalAdapterRegistry
    from aec_bench.adapters.transcript import TranscriptRole
    from aec_bench.harness.local_runtime import read_instruction
    from aec_bench.trajectory.writer import TrajectoryWriter

    instruction = read_instruction(workspace)
    if not instruction:
        _log.warning("No instruction found in workspace %s", workspace)
        return

    # Build trajectory writer so the adapter records structured traces
    traj_path = str(Path(workspace) / "trajectory.jsonl")
    trajectory_writer = TrajectoryWriter(path=traj_path)

    registry = LocalAdapterRegistry()
    adapter = registry.build(
        adapter_kind=adapter_kind,
        model_name=model,
        workspace=workspace,
        trajectory_writer=trajectory_writer,
    )

    # Declare bash tool when using tool_loop adapter so it passes the allowlist check
    tools: list = []
    if adapter_kind == "tool_loop":
        from aec_bench.contracts.task_definition import ToolSpec

        tools = [
            ToolSpec(
                name="bash",
                source="builtin",
                description="Execute a bash command in the workspace",
            )
        ]

    result = adapter.execute(AdapterRequest(instruction=instruction, tools=tools))

    # Write output.md if the adapter produced text and the file doesn't exist
    output_path = Path(workspace, "output.md")
    if not (output_path.exists() and output_path.stat().st_size > 0):
        if result.raw_output_text:
            output_path.write_text(result.raw_output_text)

    # Write conversation.jsonl from the adapter's transcript
    conversation_path = Path(workspace, "conversation.jsonl")
    with conversation_path.open("w", encoding="utf-8") as f:
        for entry in result.transcript:
            f.write(
                json.dumps(
                    {
                        "role": entry.role.value if isinstance(entry.role, TranscriptRole) else str(entry.role),
                        "content": entry.content or "",
                    }
                )
                + "\n"
            )

    # Write agent_result.json (includes cache token counts and advisor stats when available)
    agent_result_data: dict[str, int | str] = {
        "status": result.agent_output.status.value,
        "model": model,
        "adapter": adapter_kind,
        "input_tokens": result.usage_input_tokens or 0,
        "output_tokens": result.usage_output_tokens or 0,
        "cache_read_tokens": result.usage_cache_read_tokens or 0,
        "cache_write_tokens": result.usage_cache_write_tokens or 0,
    }
    if result.usage_advisor_calls is not None:
        agent_result_data["advisor_calls"] = result.usage_advisor_calls
    if result.usage_advisor_input_tokens is not None:
        agent_result_data["advisor_input_tokens"] = result.usage_advisor_input_tokens
    if result.usage_advisor_output_tokens is not None:
        agent_result_data["advisor_output_tokens"] = result.usage_advisor_output_tokens
    Path(workspace, "agent_result.json").write_text(
        json.dumps(agent_result_data, indent=2),
    )
