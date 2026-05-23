# ABOUTME: Task selection helpers for filtering validated task definitions in aec-bench.
# ABOUTME: Applies experiment-facing filters while keeping lifecycle policy visible and testable.

from fnmatch import fnmatch

from aec_bench.contracts.task_definition import Difficulty, Lifecycle, TaskDefinition, Visibility


def select_tasks(
    tasks: list[TaskDefinition],
    *,
    domains: list[str] | None = None,
    difficulties: list[Difficulty] | None = None,
    lifecycle: list[Lifecycle] | None = None,
    visibility: list[Visibility] | None = None,
    tags: list[str] | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[TaskDefinition]:
    return [
        task
        for task in tasks
        if _matches(
            task,
            domains=domains,
            difficulties=difficulties,
            lifecycle=lifecycle,
            visibility=visibility,
            tags=tags,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
        )
    ]


def _matches(
    task: TaskDefinition,
    *,
    domains: list[str] | None,
    difficulties: list[Difficulty] | None,
    lifecycle: list[Lifecycle] | None,
    visibility: list[Visibility] | None,
    tags: list[str] | None,
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
) -> bool:
    if lifecycle is not None and task.lifecycle not in lifecycle:
        return False
    if domains is not None and task.domain not in domains:
        return False
    if difficulties is not None and task.difficulty not in difficulties:
        return False
    if visibility is not None and task.visibility not in visibility:
        return False
    if tags is not None and not all(tag in task.tags for tag in tags):
        return False
    if include_patterns is not None and not any(fnmatch(task.task_id, pattern) for pattern in include_patterns):
        return False
    if exclude_patterns is not None and any(fnmatch(task.task_id, pattern) for pattern in exclude_patterns):
        return False
    return True
