# ABOUTME: Dataset integrity verification — compare stored hashes against live task files.
# ABOUTME: Returns structured results for CLI (exit codes) and TUI (display) consumption.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.dataset import DatasetTaskEntry
from aec_bench.dataset.hashing import hash_task_directory


@dataclass(frozen=True)
class IntegrityResult:
    """Result of verifying dataset task hashes against disk."""

    verified: int = 0
    drifted: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        return len(self.drifted) == 0 and len(self.missing) == 0


def verify_dataset_integrity(
    tasks: list[DatasetTaskEntry],
    *,
    project_root: Path,
) -> IntegrityResult:
    """Verify that all tasks on disk match their manifest hashes."""
    verified = 0
    drifted: list[str] = []
    missing: list[str] = []

    for task in tasks:
        task_dir = project_root / task.task_path
        if not task_dir.exists():
            missing.append(task.task_id)
            continue
        current_hash = hash_task_directory(task_dir)
        if current_hash != task.content_hash:
            drifted.append(task.task_id)
        else:
            verified += 1

    return IntegrityResult(verified=verified, drifted=tuple(drifted), missing=tuple(missing))
