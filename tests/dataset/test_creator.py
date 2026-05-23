# ABOUTME: Tests for dataset creator — builds manifests from task definitions on disk.
# ABOUTME: Verifies description metadata extraction, hashing, and storage integration.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.contracts.dataset import DatasetManifest, DatasetSource
from aec_bench.contracts.task_definition import Difficulty
from aec_bench.dataset.creator import create_dataset_from_tasks
from aec_bench.dataset.storage import read_manifest
from tests.support.task_factories import make_task_definition


def _create_task_on_disk(
    tasks_root: Path,
    task_id: str,
    domain: str = "electrical",
    difficulty: str = "medium",
) -> Path:
    """Create a minimal task directory on disk for testing."""
    task_dir = tasks_root / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.toml").write_text(f'[metadata]\ndifficulty = "{difficulty}"')
    (task_dir / "instruction.md").write_text(f"# Task {task_id}")
    return task_dir


class TestCreateDatasetFromTasks:
    def test_creates_manifest_on_disk(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        datasets_root = tmp_path / "datasets"
        task_id = "electrical/voltage-drop/instance-001"
        _create_task_on_disk(tasks_root, task_id)

        task_def = make_task_definition(
            task_id=task_id,
            domain="electrical",
            difficulty=Difficulty.MEDIUM,
        )
        source = DatasetSource(method="manual")

        manifest = create_dataset_from_tasks(
            name="test-suite",
            version="1.0.0",
            tasks=[task_def],
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
            summary="Test dataset",
        )

        assert isinstance(manifest, DatasetManifest)
        manifest_path = datasets_root / "test-suite" / "1.0.0" / "manifest.json"
        assert manifest_path.is_file()

    def test_manifest_has_correct_metadata(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        datasets_root = tmp_path / "datasets"

        task_ids = [
            ("electrical/vd/inst-1", "electrical", Difficulty.EASY),
            ("electrical/vd/inst-2", "electrical", Difficulty.MEDIUM),
            ("civil/rational/inst-1", "civil", Difficulty.HARD),
        ]
        task_defs = []
        for tid, domain, diff in task_ids:
            _create_task_on_disk(tasks_root, tid, domain=domain, difficulty=diff.value)
            task_defs.append(
                make_task_definition(
                    task_id=tid,
                    domain=domain,
                    difficulty=diff,
                    tags=["test"],
                )
            )

        source = DatasetSource(method="manual")
        manifest = create_dataset_from_tasks(
            name="multi-domain",
            version="1.0.0",
            tasks=task_defs,
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
            summary="Multi-domain test",
            purpose="Test description building",
        )

        assert manifest.name == "multi-domain"
        assert manifest.version == "1.0.0"
        assert manifest.description.task_count == 3
        assert set(manifest.description.domains) == {"civil", "electrical"}
        assert manifest.description.difficulty_distribution == {
            "easy": 1,
            "medium": 1,
            "hard": 1,
        }
        assert manifest.description.summary == "Multi-domain test"
        assert manifest.description.purpose == "Test description building"

    def test_manifest_tasks_have_content_hashes(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        datasets_root = tmp_path / "datasets"
        task_id = "electrical/vd/inst-1"
        _create_task_on_disk(tasks_root, task_id)

        task_def = make_task_definition(task_id=task_id, domain="electrical")
        source = DatasetSource(method="manual")

        manifest = create_dataset_from_tasks(
            name="suite",
            version="1.0.0",
            tasks=[task_def],
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
        )

        assert len(manifest.tasks) == 1
        entry = manifest.tasks[0]
        assert entry.task_id == task_id
        assert len(entry.content_hash) == 64  # SHA256 hex digest

    def test_manifest_content_hash_is_set(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        datasets_root = tmp_path / "datasets"
        task_id = "electrical/vd/inst-1"
        _create_task_on_disk(tasks_root, task_id)

        task_def = make_task_definition(task_id=task_id, domain="electrical")
        source = DatasetSource(method="manual")

        manifest = create_dataset_from_tasks(
            name="suite",
            version="1.0.0",
            tasks=[task_def],
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
        )

        assert len(manifest.content_hash) == 64

    def test_round_trip_through_storage(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        datasets_root = tmp_path / "datasets"
        task_id = "electrical/vd/inst-1"
        _create_task_on_disk(tasks_root, task_id)

        task_def = make_task_definition(task_id=task_id, domain="electrical")
        source = DatasetSource(method="manual")

        manifest = create_dataset_from_tasks(
            name="suite",
            version="1.0.0",
            tasks=[task_def],
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
        )

        manifest_path = datasets_root / "suite" / "1.0.0" / "manifest.json"
        loaded = read_manifest(manifest_path)
        assert loaded.name == manifest.name
        assert loaded.content_hash == manifest.content_hash
        assert len(loaded.tasks) == len(manifest.tasks)

    def test_overwrite_false_raises_on_duplicate(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        datasets_root = tmp_path / "datasets"
        task_id = "electrical/vd/inst-1"
        _create_task_on_disk(tasks_root, task_id)

        task_def = make_task_definition(task_id=task_id, domain="electrical")
        source = DatasetSource(method="manual")

        create_dataset_from_tasks(
            name="suite",
            version="1.0.0",
            tasks=[task_def],
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
        )

        with pytest.raises(FileExistsError):
            create_dataset_from_tasks(
                name="suite",
                version="1.0.0",
                tasks=[task_def],
                tasks_root=tasks_root,
                datasets_root=datasets_root,
                source=source,
            )

    def test_overwrite_true_replaces_existing(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        datasets_root = tmp_path / "datasets"
        task_id = "electrical/vd/inst-1"
        _create_task_on_disk(tasks_root, task_id)

        task_def = make_task_definition(task_id=task_id, domain="electrical")
        source = DatasetSource(method="manual")

        create_dataset_from_tasks(
            name="suite",
            version="1.0.0",
            tasks=[task_def],
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
        )

        # Modify task content and recreate with overwrite
        (tasks_root / task_id / "instruction.md").write_text("# Updated")

        manifest = create_dataset_from_tasks(
            name="suite",
            version="1.0.0",
            tasks=[task_def],
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
            overwrite=True,
        )

        manifest_path = datasets_root / "suite" / "1.0.0" / "manifest.json"
        loaded = read_manifest(manifest_path)
        assert loaded.content_hash == manifest.content_hash

    def test_collects_standards_from_metadata(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        datasets_root = tmp_path / "datasets"
        task_id = "electrical/vd/inst-1"
        _create_task_on_disk(tasks_root, task_id)

        task_def = make_task_definition(
            task_id=task_id,
            domain="electrical",
            metadata={"standard": "AS3008", "jurisdiction": "au"},
        )
        source = DatasetSource(method="manual")

        manifest = create_dataset_from_tasks(
            name="suite",
            version="1.0.0",
            tasks=[task_def],
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
        )

        assert "AS3008" in manifest.description.standards

    def test_skips_tasks_with_missing_directories(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        datasets_root = tmp_path / "datasets"

        # Create one task on disk, but reference two task definitions
        real_id = "electrical/vd/inst-1"
        _create_task_on_disk(tasks_root, real_id)
        ghost_id = "electrical/vd/inst-ghost"

        real_def = make_task_definition(task_id=real_id, domain="electrical")
        ghost_def = make_task_definition(task_id=ghost_id, domain="electrical")
        source = DatasetSource(method="manual")

        manifest = create_dataset_from_tasks(
            name="suite",
            version="1.0.0",
            tasks=[real_def, ghost_def],
            tasks_root=tasks_root,
            datasets_root=datasets_root,
            source=source,
        )

        assert len(manifest.tasks) == 1
        assert manifest.tasks[0].task_id == real_id
