# ABOUTME: Manifest-driven trial planning and bounded batching for the Python harness.
# ABOUTME: Expands tasks, agents, and repetitions into deterministic planned trials.

from pathlib import Path

from aec_bench.contracts.experiment_manifest import ExperimentManifest
from aec_bench.contracts.task_definition import Lifecycle, TaskDefinition
from aec_bench.harness.trial import PlannedTrial, build_trial_id
from aec_bench.tasks.selector import select_tasks


def select_manifest_tasks(
    tasks: list[TaskDefinition],
    manifest: ExperimentManifest,
    *,
    datasets_root: Path | None = None,
    project_root: Path | None = None,
) -> list[TaskDefinition]:
    selector = manifest.tasks

    if selector.dataset is not None:
        from aec_bench.config import load_config
        from aec_bench.dataset.publication import resolve_dataset, verify_resolved_dataset

        config = load_config(project_root)
        resolved_root = datasets_root or config.datasets_root
        resolved_project = project_root or config.project_root
        resolved = resolve_dataset(
            datasets_root=resolved_root,
            selector=selector.dataset,
            project_root=resolved_project,
        )
        if resolved is None:
            raise ValueError("resolved dataset reference is not available")
        integrity = verify_resolved_dataset(
            resolved,
            datasets_root=resolved_root,
            project_root=resolved_project,
        )
        if not integrity.is_clean:
            raise ValueError("resolved dataset task materialisation failed integrity verification")
        dataset_task_ids = {task.task_id for task in resolved.manifest.tasks}
        available_task_ids = {task.task_id for task in tasks}
        missing_task_ids = sorted(dataset_task_ids - available_task_ids)
        if missing_task_ids:
            raise ValueError(f"resolved dataset tasks are not registered: {', '.join(missing_task_ids)}")
        tasks = [task for task in tasks if task.task_id in dataset_task_ids]

    return select_tasks(
        tasks,
        domains=manifest.tasks.domains or None,
        difficulties=manifest.tasks.difficulties or None,
        include_patterns=manifest.tasks.include_patterns or None,
        exclude_patterns=manifest.tasks.exclude_patterns or None,
        lifecycle=[
            Lifecycle.PROPOSED,
            Lifecycle.ACTIVE,
            Lifecycle.DEPRECATED,
            Lifecycle.RETIRED,
        ],
    )


def build_trial_plan(
    manifest: ExperimentManifest,
    tasks: list[TaskDefinition],
) -> list[PlannedTrial]:
    selected_tasks = sorted(tasks, key=lambda task: task.task_id)
    plan: list[PlannedTrial] = []
    for task in selected_tasks:
        for agent in manifest.agents:
            for repetition in range(1, manifest.repetitions + 1):
                plan.append(
                    PlannedTrial(
                        trial_id=build_trial_id(
                            experiment_id=manifest.experiment_id,
                            task_id=task.task_id,
                            agent_name=agent.name,
                            repetition=repetition,
                        ),
                        experiment_id=manifest.experiment_id,
                        task_id=task.task_id,
                        agent=agent,
                        compute=manifest.compute,
                        repetition=repetition,
                    )
                )
    return plan


def batch_planned_trials(
    planned_trials: list[PlannedTrial],
    *,
    max_concurrency: int,
) -> list[list[PlannedTrial]]:
    if max_concurrency <= 0:
        raise ValueError("max_concurrency must be positive")
    return [planned_trials[index : index + max_concurrency] for index in range(0, len(planned_trials), max_concurrency)]
