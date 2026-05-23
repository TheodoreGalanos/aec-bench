# ABOUTME: In-memory registry for benchmark task definitions in aec-bench Python.
# ABOUTME: Loads real task instances once and supports lookup plus experiment filters.

import logging
from pathlib import Path

from aec_bench.contracts.task_definition import Difficulty, Lifecycle, TaskDefinition, Visibility
from aec_bench.tasks.loader import LoadError, iter_task_instance_dirs, load_task_definition
from aec_bench.tasks.selector import select_tasks

logger = logging.getLogger(__name__)


class TaskRegistry:
    def __init__(self, tasks_root: Path) -> None:
        self.tasks_root = tasks_root
        self._tasks: dict[str, TaskDefinition] = {}
        self._load_errors: list[tuple[Path, str]] = []

    def reload(self) -> None:
        tasks: dict[str, TaskDefinition] = {}
        errors: list[tuple[Path, str]] = []
        for instance_dir in iter_task_instance_dirs(self.tasks_root):
            try:
                task = load_task_definition(instance_dir, self.tasks_root)
                tasks[task.task_id] = task
            except LoadError as exc:
                logger.warning("failed to load task at %s: %s", instance_dir, exc)
                errors.append((instance_dir, str(exc)))
        self._tasks = tasks
        self._load_errors = errors

    @property
    def load_errors(self) -> list[tuple[Path, str]]:
        return list(self._load_errors)

    def get(self, task_id: str) -> TaskDefinition | None:
        return self._tasks.get(task_id)

    def all(self) -> list[TaskDefinition]:
        return list(self._tasks.values())

    def filter(
        self,
        *,
        domains: list[str] | None = None,
        difficulties: list[Difficulty] | None = None,
        lifecycle: list[Lifecycle] | None = None,
        visibility: list[Visibility] | None = None,
        tags: list[str] | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[TaskDefinition]:
        return select_tasks(
            self.all(),
            domains=domains,
            difficulties=difficulties,
            lifecycle=lifecycle,
            visibility=visibility,
            tags=tags,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )
