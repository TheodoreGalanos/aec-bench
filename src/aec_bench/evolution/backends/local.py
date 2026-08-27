# ABOUTME: Composes local evolution fitness runs through the artifact-task application path.
# ABOUTME: Materializes each evolved snapshot as explicit agent configuration before planning trials.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from aec_bench.contracts.evolution import WorkspaceSnapshot
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig, ExperimentManifest, TaskSelector
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.evaluation import (
    CandidateChecks,
    CandidateEvaluationBatch,
    validate_trial_records,
)
from aec_bench.evolution.snapshot import serialise_snapshot
from aec_bench.harness.artifact_tasks import LocalTaskRuntime, run_experiment, single_attempt
from aec_bench.tasks.instance import ResolvedTaskInstance, resolve_instance_paths
from aec_bench.tasks.loader import load_task_definition
from aec_bench.trials import build_trial_id, plan_trials


def build_local_checks(
    *,
    task_dirs: Sequence[Path],
    model: str,
    experiment_id: str,
    workspace_root: Path | None = None,
    candidate_identity: bool = True,
    adapter: str = "rlm",
    timeout: int = 1800,
    backend: str = "local",
    agent_config: AgentConfig | None = None,
) -> CandidateChecks:
    """Build one local capability for planning and checking candidates."""
    resolved_tasks: list[ResolvedTaskInstance] | None = None

    def plan(batch_size: int, cycle: int) -> CandidateEvaluationBatch:
        nonlocal resolved_tasks
        if batch_size < 1:
            raise ValueError("evaluation batch size must be positive")
        if cycle < 0:
            raise ValueError("evaluation batch cycle must be non-negative")
        if resolved_tasks is None:
            resolved_tasks = _resolve_task_directories(task_dirs)
        selected = _select_task_batch(
            resolved_tasks,
            batch_size=batch_size,
            start_index=cycle * batch_size,
        )
        if not selected:
            raise ValueError("evaluation batch requires at least one resolved task")
        agent = agent_config or AgentConfig(name="evolution-agent", adapter=adapter, model=model)
        manifest = ExperimentManifest(
            experiment_id=f"{experiment_id}-cycle-{cycle}",
            name=f"Evolution fitness cycle {cycle}",
            tasks=TaskSelector(include_patterns=[task.task.task_id for task in selected]),
            agents=[agent],
            compute=ComputeConfig(backend=backend, timeout_override=timeout),
            repetitions=1,
        )
        trials = plan_trials(
            manifest.experiment_id,
            tasks=[task.task for task in selected],
            agents=manifest.agents,
            compute=manifest.compute,
            repetitions=manifest.repetitions,
        )
        return CandidateEvaluationBatch(
            tasks=tuple(selected),
            trials=tuple(trials),
            evaluation_case_ids=tuple(
                f"{trial.task_id}::agent={trial.agent.name}::attempt={trial.repetition}" for trial in trials
            ),
            cycle=cycle,
        )

    def run(snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch) -> tuple[TrialRecord, ...]:
        """Execute an exact planned batch through the local artifact runtime.

        Selection checks namespace experiment and trial identities by
        candidate. Revision checks can keep their planned experiment identity;
        the AVO composition supplies unique revision trial IDs.
        """
        snapshot_prompt = serialise_snapshot(snapshot)
        trials = tuple(
            replace(
                trial,
                experiment_id=(
                    trial.experiment_id
                    if not candidate_identity
                    else f"{trial.experiment_id}--candidate-{snapshot.candidate_id}"
                ),
                trial_id=(
                    trial.trial_id
                    if not candidate_identity
                    else build_trial_id(
                        experiment_id=f"{trial.experiment_id}--candidate-{snapshot.candidate_id}",
                        task_id=trial.task_id,
                        agent_name=trial.agent.name,
                        repetition=trial.repetition,
                    )
                ),
                agent=trial.agent.model_copy(update={"system_prompt": snapshot_prompt}),
            )
            for trial in batch.trials
        )
        runtime = LocalTaskRuntime(agent_files=_agent_files(workspace_root))
        records = run_experiment(
            runtime=runtime,
            tasks=batch.tasks,
            trials=trials,
            recipe=single_attempt(),
        )
        validate_trial_records(records, batch)
        return tuple(records)

    return CandidateChecks(plan=plan, run=run)


def _resolve_task_directories(task_dirs: Sequence[Path]) -> list[ResolvedTaskInstance]:
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


__all__ = ("build_local_checks",)
