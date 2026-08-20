# ABOUTME: Composes local evolution fitness runs through the artifact-task application path.
# ABOUTME: Materializes each evolved snapshot as explicit agent configuration before planning trials.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.evolution import WorkspaceSnapshot
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig, ExperimentManifest, TaskSelector
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.application import CandidateEvaluator
from aec_bench.evolution.snapshot import serialise_snapshot
from aec_bench.harness.artifact_tasks import LocalTaskRuntime, run_experiment, single_attempt
from aec_bench.harness.scheduler import build_trial_plan
from aec_bench.tasks.instance import ResolvedTaskInstance, resolve_instance_paths
from aec_bench.tasks.loader import load_task_definition


def make_stub_candidate_evaluator(records: list[TrialRecord]) -> CandidateEvaluator:
    """Return fixed records for deterministic evolution tests."""

    def solve(_snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
        return records[:batch_size]

    return solve


def make_local_candidate_evaluator(
    *,
    task_dirs: list[Path],
    model: str,
    experiment_id: str,
    adapter: str = "rlm",
    timeout: int = 1800,
    workspace_root: Path | None = None,
) -> CandidateEvaluator:
    """Compose each evolution fitness batch through planning and run_experiment()."""

    task_cursor = 0
    call_count = 0
    resolved_tasks: list[ResolvedTaskInstance] | None = None

    def solve(snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
        nonlocal call_count, resolved_tasks, task_cursor
        if not task_dirs:
            return []
        if resolved_tasks is None:
            resolved_tasks = _resolve_task_directories(task_dirs)
        selected = _select_task_batch(resolved_tasks, batch_size=batch_size, start_index=task_cursor)
        if not selected:
            return []
        task_cursor = (task_cursor + len(selected)) % len(resolved_tasks)
        agent = AgentConfig(
            name="evolution-agent",
            adapter=adapter,
            model=model,
            system_prompt=serialise_snapshot(snapshot),
        )
        manifest = ExperimentManifest(
            experiment_id=f"{experiment_id}-cycle-{call_count}",
            name=f"Evolution fitness cycle {call_count}",
            tasks=TaskSelector(include_patterns=[task.task.task_id for task in selected]),
            agents=[agent],
            compute=ComputeConfig(backend="local", timeout_override=timeout),
            repetitions=1,
        )
        trials = build_trial_plan(manifest, [task.task for task in selected])
        runtime = LocalTaskRuntime(agent_files=_agent_files(workspace_root))
        call_count += 1
        return run_experiment(
            runtime=runtime,
            tasks=selected,
            trials=trials,
            recipe=single_attempt(),
        )

    return solve


def _resolve_task_directories(task_dirs: list[Path]) -> list[ResolvedTaskInstance]:
    resolved: list[ResolvedTaskInstance] = []
    for task_dir in task_dirs:
        tasks_root = _find_tasks_root(task_dir)
        task = load_task_definition(task_dir, tasks_root)
        resolved.append(resolve_instance_paths(task, task_dir))
    return resolved


def _find_tasks_root(task_dir: Path) -> Path:
    candidate = task_dir.resolve()
    while candidate != candidate.parent:
        if (candidate / "generation-manifest.json").is_file():
            return candidate
        if candidate.name == "tasks":
            return candidate
        candidate = candidate.parent
    return task_dir.parent.resolve()


def _select_task_batch(
    tasks: list[ResolvedTaskInstance],
    *,
    batch_size: int,
    start_index: int,
) -> list[ResolvedTaskInstance]:
    if not tasks:
        return []
    count = min(batch_size, len(tasks))
    return [tasks[(start_index + offset) % len(tasks)] for offset in range(count)]


def _agent_files(workspace_root: Path | None) -> dict[str, Path]:
    if workspace_root is None:
        return {}
    config = workspace_root / "tool_loop.toml"
    return {"tool_loop.toml": config} if config.is_file() else {}


__all__ = ("make_local_candidate_evaluator", "make_stub_candidate_evaluator")
