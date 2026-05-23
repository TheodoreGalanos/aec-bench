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
) -> list[TaskDefinition]:
    selector = manifest.tasks

    if selector.dataset is not None:
        from aec_bench.config import load_config
        from aec_bench.dataset.storage import resolve_dataset

        resolved_root = datasets_root or load_config().datasets_root
        dataset_manifest = resolve_dataset(resolved_root, selector.dataset)
        if dataset_manifest is not None:
            dataset_task_ids = {t.task_id for t in dataset_manifest.tasks}
            tasks = [t for t in tasks if t.task_id in dataset_task_ids]

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
                        compute_backend=manifest.compute.backend,
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
