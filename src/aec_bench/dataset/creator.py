# ABOUTME: Creates semantic schema-2 dataset manifests from validated task definitions.
# ABOUTME: Fails on missing selected tasks and delegates immutable persistence to dataset storage.

from __future__ import annotations

from pathlib import Path
from typing import cast

from aec_bench.contracts.dataset import (
    DatasetGeneration,
    DatasetManifest,
    DatasetTaskEntry,
    DatasetTaskKind,
)
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.dataset.storage import write_manifest

_TASK_KINDS = {"artifact", "lifecycle", "world"}


def _task_kind(task: TaskDefinition) -> DatasetTaskKind:
    raw = task.metadata.get("task_kind", "artifact")
    if not isinstance(raw, str) or raw not in _TASK_KINDS:
        raise ValueError(f"task {task.task_id} has unsupported task_kind: {raw!r}")
    return cast(DatasetTaskKind, raw)


def create_dataset_from_tasks(
    *,
    dataset_id: str,
    tasks: list[TaskDefinition],
    tasks_root: Path,
    datasets_root: Path,
    description: str,
    generation: DatasetGeneration | None = None,
) -> DatasetManifest:
    """Create and immutably store one semantic dataset manifest."""

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

    manifest = DatasetManifest(
        dataset_id=dataset_id,
        description=description,
        tasks=tuple(entries),
        generation=generation,
    )
    write_manifest(datasets_root, manifest)
    return manifest


__all__ = ("create_dataset_from_tasks",)
