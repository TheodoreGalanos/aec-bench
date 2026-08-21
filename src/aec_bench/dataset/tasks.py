# ABOUTME: Loads concrete task values from the task-kind declarations in a dataset manifest.
# ABOUTME: Keeps dataset identity separate from artifact and Interactive World task semantics.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.dataset import DatasetManifest
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.tasks.loader import load_task_definition
from aec_bench.worlds.tasks import WorldTask, load_world_task


def load_dataset_tasks(
    manifest: DatasetManifest,
    *,
    project_root: Path,
    tasks_root: Path,
) -> list[TaskDefinition | WorldTask]:
    """Load concrete tasks in declared dataset order."""

    loaded: list[TaskDefinition | WorldTask] = []
    for entry in manifest.tasks:
        task_dir = project_root / entry.path
        if entry.task_kind == "artifact":
            loaded_task: TaskDefinition | WorldTask = load_task_definition(task_dir, tasks_root)
        elif entry.task_kind == "world":
            loaded_task = load_world_task(task_dir, tasks_root)
        else:
            raise ValueError(f"dataset lifecycle task loading is not supported by this task package: {entry.task_id}")
        if loaded_task.task_id != entry.task_id:
            raise ValueError(f"dataset task identity does not match its path: {entry.task_id}")
        loaded.append(loaded_task)
    return loaded


__all__ = ("load_dataset_tasks",)
