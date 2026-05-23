# ABOUTME: Progress accounting helpers for Harbor-backed experiment import workflows.
# ABOUTME: Tracks deterministic import counters without coupling the harness to any UI surface.

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ImportProgressSnapshot:
    experiment_id: str
    selected_task_count: int
    discovered_trials: int = 0
    imported_trials: int = 0
    duplicate_trials: int = 0
    invalid_trials: int = 0


WorkflowStage = Literal[
    "dispatch_started",
    "dispatch_completed",
    "job_dir_identified",
    "import_started",
    "import_completed",
]


@dataclass(frozen=True)
class WorkflowProgressSnapshot:
    experiment_id: str
    stage: WorkflowStage
    selected_task_count: int
    planned_trial_count: int
    dispatch_exit_code: int | None = None
    job_dir: str | None = None
    discovered_trials: int = 0
    imported_trials: int = 0
    duplicate_trials: int = 0
    invalid_trials: int = 0


class ImportProgressTracker:
    def __init__(self, *, experiment_id: str, selected_task_count: int) -> None:
        self._experiment_id = experiment_id
        self._selected_task_count = selected_task_count
        self._discovered_trials = 0
        self._imported_trials = 0
        self._duplicate_trials = 0
        self._invalid_trials = 0

    def record_discovered(self) -> None:
        self._discovered_trials += 1

    def record_imported(self) -> None:
        self._imported_trials += 1

    def record_duplicate(self) -> None:
        self._duplicate_trials += 1

    def record_invalid(self) -> None:
        self._invalid_trials += 1

    def snapshot(self) -> ImportProgressSnapshot:
        return ImportProgressSnapshot(
            experiment_id=self._experiment_id,
            selected_task_count=self._selected_task_count,
            discovered_trials=self._discovered_trials,
            imported_trials=self._imported_trials,
            duplicate_trials=self._duplicate_trials,
            invalid_trials=self._invalid_trials,
        )


class WorkflowProgressTracker:
    def __init__(
        self,
        *,
        experiment_id: str,
        selected_task_count: int,
        planned_trial_count: int,
    ) -> None:
        self._experiment_id = experiment_id
        self._selected_task_count = selected_task_count
        self._planned_trial_count = planned_trial_count

    def dispatch_started(self) -> WorkflowProgressSnapshot:
        return self._snapshot(stage="dispatch_started")

    def dispatch_completed(self, *, exit_code: int | None) -> WorkflowProgressSnapshot:
        return self._snapshot(stage="dispatch_completed", dispatch_exit_code=exit_code)

    def job_dir_identified(self, *, job_dir: Path) -> WorkflowProgressSnapshot:
        return self._snapshot(stage="job_dir_identified", job_dir=job_dir.as_posix())

    def import_started(self, *, job_dir: Path) -> WorkflowProgressSnapshot:
        return self._snapshot(stage="import_started", job_dir=job_dir.as_posix())

    def import_completed(
        self,
        *,
        job_dir: Path,
        discovered_trials: int,
        imported_trials: int,
        duplicate_trials: int,
        invalid_trials: int,
    ) -> WorkflowProgressSnapshot:
        return self._snapshot(
            stage="import_completed",
            job_dir=job_dir.as_posix(),
            discovered_trials=discovered_trials,
            imported_trials=imported_trials,
            duplicate_trials=duplicate_trials,
            invalid_trials=invalid_trials,
        )

    def _snapshot(
        self,
        *,
        stage: WorkflowStage,
        dispatch_exit_code: int | None = None,
        job_dir: str | None = None,
        discovered_trials: int = 0,
        imported_trials: int = 0,
        duplicate_trials: int = 0,
        invalid_trials: int = 0,
    ) -> WorkflowProgressSnapshot:
        return WorkflowProgressSnapshot(
            experiment_id=self._experiment_id,
            stage=stage,
            selected_task_count=self._selected_task_count,
            planned_trial_count=self._planned_trial_count,
            dispatch_exit_code=dispatch_exit_code,
            job_dir=job_dir,
            discovered_trials=discovered_trials,
            imported_trials=imported_trials,
            duplicate_trials=duplicate_trials,
            invalid_trials=invalid_trials,
        )
