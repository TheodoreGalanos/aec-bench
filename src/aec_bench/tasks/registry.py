# ABOUTME: In-memory registry for benchmark task definitions in aec-bench Python.
# ABOUTME: Loads real task instances once and supports lookup plus experiment filters.

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from aec_bench.contracts.task_definition import Difficulty, Lifecycle, TaskDefinition, Visibility
from aec_bench.tasks.loader import LoadError, load_task_definition
from aec_bench.tasks.selector import select_tasks

logger = logging.getLogger(__name__)


class TaskDiagnosticKind(StrEnum):
    """Classification for one task that could not load."""

    MISSING_FILE = "missing_file"
    TOML_PARSE = "toml_parse"
    DECODE = "decode"
    CONTRACT = "contract_validation"
    INVALID_ID = "invalid_id"
    INVALID_KEY = "invalid_key"
    UNSAFE_PATH = "unsafe_path"
    UNSUPPORTED_VALUE = "unsupported_value"
    LOAD = "load_error"


@dataclass(frozen=True)
class TaskDiagnostic:
    """Actionable information about one invalid task package."""

    path: Path
    kind: TaskDiagnosticKind
    message: str

    @property
    def code(self) -> str:
        """Return the stable diagnostic classification."""

        return self.kind.value

    def to_dict(self) -> dict[str, str]:
        return {"path": str(self.path), "kind": self.kind.value, "message": self.message}


@dataclass(frozen=True)
class TaskRegistrySummary:
    """Counts from one registry reload."""

    discovered: int
    valid: int
    invalid: int

    def to_dict(self) -> dict[str, int]:
        return {"discovered": self.discovered, "valid": self.valid, "invalid": self.invalid}


class TaskRegistry:
    def __init__(self, tasks_root: Path) -> None:
        self.tasks_root = tasks_root
        self._tasks: dict[str, TaskDefinition] = {}
        self._load_errors: list[tuple[Path, str]] = []
        self._diagnostics: list[TaskDiagnostic] = []
        self._summary = TaskRegistrySummary(discovered=0, valid=0, invalid=0)

    def reload(self) -> TaskRegistrySummary:
        tasks: dict[str, TaskDefinition] = {}
        diagnostics: list[TaskDiagnostic] = []
        instance_dirs = _candidate_task_dirs(self.tasks_root)
        for instance_dir in instance_dirs:
            try:
                task = load_task_definition(instance_dir, self.tasks_root)
                if task.task_id in tasks:
                    raise LoadError(f"duplicate task identity key: {task.task_id}")
                tasks[task.task_id] = task
            except (LoadError, KeyError, TypeError, ValueError) as exc:
                logger.warning("failed to load task at %s: %s", instance_dir, exc)
                diagnostics.append(_diagnostic(instance_dir, str(exc)))
        self._tasks = tasks
        self._diagnostics = diagnostics
        self._load_errors = [(item.path, item.message) for item in diagnostics]
        self._summary = TaskRegistrySummary(
            discovered=len(instance_dirs),
            valid=len(tasks),
            invalid=len(diagnostics),
        )
        return self._summary

    @property
    def load_errors(self) -> list[tuple[Path, str]]:
        return list(self._load_errors)

    @property
    def valid_tasks(self) -> list[TaskDefinition]:
        """Return tasks that loaded successfully."""

        return self.all()

    @property
    def invalid_diagnostics(self) -> list[TaskDiagnostic]:
        """Return classified diagnostics from the latest reload."""

        return list(self._diagnostics)

    @property
    def summary(self) -> TaskRegistrySummary:
        return self._summary

    def require_valid(self) -> None:
        """Fail when the latest catalogue contains an invalid task."""

        if self._diagnostics:
            details = "; ".join(f"{item.path}: {item.message}" for item in self._diagnostics)
            raise ValueError(f"task catalogue contains invalid tasks: {details}")

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


def _candidate_task_dirs(tasks_root: Path) -> list[Path]:
    if not tasks_root.is_dir():
        return []
    candidates = {path.parent for path in tasks_root.rglob("task.toml")}
    candidates.update(path.parent for path in tasks_root.rglob("instruction.md"))
    task_roots = {
        candidate
        for candidate in candidates
        if (candidate / "task.toml").is_file() and (candidate / "instruction.md").is_file()
    }
    return sorted(
        candidate
        for candidate in candidates
        if not any(parent in task_roots for parent in candidate.parents if parent != candidate)
    )


def _diagnostic(instance_dir: Path, message: str) -> TaskDiagnostic:
    lowered = message.lower()
    if "missing " in lowered or "missing task.toml" in lowered:
        kind = TaskDiagnosticKind.MISSING_FILE
    elif "invalid task.toml" in lowered:
        kind = TaskDiagnosticKind.DECODE if "decode" in lowered or "utf" in lowered else TaskDiagnosticKind.TOML_PARSE
    elif "entity id" in lowered or "uuid" in lowered:
        kind = TaskDiagnosticKind.INVALID_ID
    elif "entity key" in lowered or "identity key" in lowered or "task path is not" in lowered:
        kind = TaskDiagnosticKind.INVALID_KEY
    elif "unsafe" in lowered or "escape" in lowered or "portable" in lowered or "path must be relative" in lowered:
        kind = TaskDiagnosticKind.UNSAFE_PATH
    elif "unsupported" in lowered or "lifecycle" in lowered or "visibility" in lowered or "difficulty" in lowered:
        kind = TaskDiagnosticKind.UNSUPPORTED_VALUE
    elif "invalid task definition" in lowered or "invalid task metadata" in lowered or "validation error" in lowered:
        kind = TaskDiagnosticKind.CONTRACT
    else:
        kind = TaskDiagnosticKind.LOAD
    return TaskDiagnostic(path=instance_dir, kind=kind, message=message)


__all__ = (
    "TaskDiagnostic",
    "TaskDiagnosticKind",
    "TaskRegistry",
    "TaskRegistrySummary",
)
