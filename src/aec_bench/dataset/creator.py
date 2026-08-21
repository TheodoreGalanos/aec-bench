# ABOUTME: Composes semantic schema-2 dataset manifests from validated task definitions.
# ABOUTME: Keeps manifest construction separate from immutable dataset storage.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.dataset import (
    DatasetGeneration,
    DatasetManifest,
    DatasetTaskEntry,
    DatasetTaskKind,
)
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.worlds.tasks import WorldTask


def _task_kind(task: TaskDefinition | WorldTask) -> DatasetTaskKind:
    if isinstance(task, WorldTask):
        return "world"
    if isinstance(task, TaskDefinition):
        return "artifact"
    raise TypeError(f"unsupported dataset task type: {type(task).__name__}")


def compose_dataset(
    *,
    dataset_id: str,
    tasks: list[TaskDefinition | WorldTask],
    tasks_root: Path,
    description: str,
    generation: DatasetGeneration | None = None,
) -> DatasetManifest:
    """Build one semantic dataset manifest without storing it."""

    project_root = tasks_root.parent.resolve()
    entries: list[DatasetTaskEntry] = []
    for task in sorted(tasks, key=lambda item: item.task_id):
        task_dir = (tasks_root / task.task_id).resolve()
        if not task_dir.is_dir():
            raise FileNotFoundError(f"selected task directory is missing: {task_dir}")
        try:
            relative_path = task_dir.relative_to(project_root).as_posix()
        except ValueError as error:
            raise ValueError(f"selected task is outside the project root: {task_dir}") from error
        entries.append(
            DatasetTaskEntry(
                task_id=task.task_id,
                path=relative_path,
                task_kind=_task_kind(task),
            )
        )

    return DatasetManifest(
        dataset_id=dataset_id,
        description=description,
        tasks=tuple(entries),
        generation=generation,
    )


__all__ = ("compose_dataset",)
