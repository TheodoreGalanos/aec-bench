# ABOUTME: Tests for dataset integrity verification — hash comparison against manifest.
# ABOUTME: Uses tmp_path to create known-good and drifted task directories.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.dataset import DatasetTaskEntry
from aec_bench.dataset.hashing import hash_task_directory
from aec_bench.dataset.integrity import IntegrityResult, verify_dataset_integrity


def test_verify_clean_dataset(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "electrical" / "vd"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text("content")
    real_hash = hash_task_directory(task_dir)
    entry = DatasetTaskEntry(
        task_id="electrical/vd",
        task_path="tasks/electrical/vd",
        content_hash=real_hash,
        domain="electrical",
        difficulty="easy",
    )
    result = verify_dataset_integrity([entry], project_root=tmp_path)
    assert result.is_clean
    assert result.verified == 1
    assert len(result.drifted) == 0
    assert len(result.missing) == 0


def test_verify_drifted_task(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "electrical" / "vd"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text("original")
    original_hash = hash_task_directory(task_dir)
    (task_dir / "task.toml").write_text("modified")
    entry = DatasetTaskEntry(
        task_id="electrical/vd",
        task_path="tasks/electrical/vd",
        content_hash=original_hash,
        domain="electrical",
        difficulty="easy",
    )
    result = verify_dataset_integrity([entry], project_root=tmp_path)
    assert not result.is_clean
    assert "electrical/vd" in result.drifted


def test_verify_missing_task(tmp_path: Path) -> None:
    entry = DatasetTaskEntry(
        task_id="electrical/gone",
        task_path="tasks/electrical/gone",
        content_hash="abc123",
        domain="electrical",
        difficulty="easy",
    )
    result = verify_dataset_integrity([entry], project_root=tmp_path)
    assert not result.is_clean
    assert "electrical/gone" in result.missing


def test_integrity_result_is_frozen() -> None:
    result = IntegrityResult(verified=1, drifted=(), missing=())
    assert isinstance(result.drifted, tuple)
    assert isinstance(result.missing, tuple)


def test_verify_mixed_dataset(tmp_path: Path) -> None:
    """A dataset with clean, drifted, and missing tasks is correctly categorised."""
    # Clean task
    clean_dir = tmp_path / "tasks" / "electrical" / "clean"
    clean_dir.mkdir(parents=True)
    (clean_dir / "task.toml").write_text("unchanged")
    clean_hash = hash_task_directory(clean_dir)

    # Drifted task
    drift_dir = tmp_path / "tasks" / "electrical" / "drift"
    drift_dir.mkdir(parents=True)
    (drift_dir / "task.toml").write_text("original")
    drift_hash = hash_task_directory(drift_dir)
    (drift_dir / "task.toml").write_text("modified")

    entries = [
        DatasetTaskEntry(
            task_id="electrical/clean",
            task_path="tasks/electrical/clean",
            content_hash=clean_hash,
            domain="electrical",
            difficulty="easy",
        ),
        DatasetTaskEntry(
            task_id="electrical/drift",
            task_path="tasks/electrical/drift",
            content_hash=drift_hash,
            domain="electrical",
            difficulty="easy",
        ),
        DatasetTaskEntry(
            task_id="electrical/gone",
            task_path="tasks/electrical/gone",
            content_hash="deadbeef",
            domain="electrical",
            difficulty="easy",
        ),
    ]

    result = verify_dataset_integrity(entries, project_root=tmp_path)
    assert not result.is_clean
    assert result.verified == 1
    assert "electrical/drift" in result.drifted
    assert "electrical/gone" in result.missing
    assert "electrical/clean" not in result.drifted
    assert "electrical/clean" not in result.missing


def test_verify_empty_task_list(tmp_path: Path) -> None:
    """An empty task list is trivially clean."""
    # Note: DatasetManifest requires non-empty tasks, but the integrity
    # function accepts any list for flexibility.
    result = verify_dataset_integrity([], project_root=tmp_path)
    assert result.is_clean
    assert result.verified == 0
