# ABOUTME: Manifest-driven trial planning and bounded batching for the Python harness.
# ABOUTME: Expands tasks, agents, and repetitions into deterministic planned trials.

from collections.abc import Sequence
from pathlib import Path

from aec_bench.contracts.experiment_manifest import ExperimentManifest
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.tasks.selector import select_tasks, validate_execution_tasks
from aec_bench.trials import PlannedTrial
from aec_bench.worlds.tasks import WorldTask


def select_manifest_tasks(
    tasks: list[TaskDefinition],
    manifest: ExperimentManifest,
    *,
    datasets_root: Path | None = None,
    project_root: Path | None = None,
    tasks_root: Path | None = None,
) -> list[TaskDefinition]:
    """Select artifact tasks for the existing artifact-only harness callers."""

    selected = select_manifest_task_values(
        tasks,
        manifest,
        datasets_root=datasets_root,
        project_root=project_root,
        tasks_root=tasks_root,
    )
    if any(isinstance(task, WorldTask) for task in selected):
        raise ValueError("artifact harness cannot execute Interactive World dataset entries")
    return [task for task in selected if isinstance(task, TaskDefinition)]


def select_manifest_task_values(
    tasks: Sequence[TaskDefinition | WorldTask],
    manifest: ExperimentManifest,
    *,
    datasets_root: Path | None = None,
    project_root: Path | None = None,
    tasks_root: Path | None = None,
) -> list[TaskDefinition | WorldTask]:
    """Select concrete artifact and world values for the top-level run application."""

    tasks = list(tasks)
    selector = manifest.tasks

    if selector.dataset is not None:
        from aec_bench.config import load_config
        from aec_bench.dataset.publication import resolve_dataset, verify_resolved_dataset
        from aec_bench.dataset.tasks import load_dataset_tasks

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
        tasks = load_dataset_tasks(
            resolved.manifest,
            project_root=resolved_project,
            tasks_root=tasks_root or resolved_project / "tasks",
        )

    selected = select_tasks(
        tasks,
        domains=manifest.tasks.domains or None,
        difficulties=manifest.tasks.difficulties or None,
        include_patterns=manifest.tasks.include_patterns or None,
        exclude_patterns=manifest.tasks.exclude_patterns or None,
        lifecycle=manifest.tasks.lifecycle_filter,
        visibility=manifest.tasks.visibility_filter,
    )
    validate_execution_tasks(selected, permitted_visibility=manifest.tasks.visibility_filter)
    return selected


def batch_planned_trials(
    planned_trials: list[PlannedTrial],
    *,
    max_concurrency: int,
) -> list[list[PlannedTrial]]:
    if max_concurrency <= 0:
        raise ValueError("max_concurrency must be positive")
    return [planned_trials[index : index + max_concurrency] for index in range(0, len(planned_trials), max_concurrency)]
