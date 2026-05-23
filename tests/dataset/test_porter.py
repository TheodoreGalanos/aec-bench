# ABOUTME: Tests for dataset export/import (porter) — archive creation and round-trip unpacking.
# ABOUTME: Verifies tar.gz contents, integrity checks, and manifest re-registration.

from __future__ import annotations

import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aec_bench.contracts.dataset import (
    DatasetDescription,
    DatasetManifest,
    DatasetSource,
    DatasetTaskEntry,
)
from aec_bench.dataset.hashing import hash_task_directory
from aec_bench.dataset.porter import export_dataset, import_dataset
from aec_bench.dataset.storage import read_manifest


def _make_task_dir(root: Path, task_path: str) -> tuple[Path, str]:
    """Create a minimal task directory with some content and return (path, hash)."""
    task_dir = root / task_path
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "instruction.md").write_text("Solve this task.", encoding="utf-8")
    (task_dir / "ground_truth.json").write_text('{"answer": 42}', encoding="utf-8")
    content_hash = hash_task_directory(task_dir)
    return task_dir, content_hash


def _make_manifest(
    project_root: Path,
    name: str = "test-suite",
    version: str = "1.0.0",
    task_paths: list[str] | None = None,
) -> DatasetManifest:
    """Build a manifest with real task directories on disk."""
    if task_paths is None:
        task_paths = ["tasks/electrical/voltage-drop/instance-0"]

    tasks = []
    for task_path in task_paths:
        _, content_hash = _make_task_dir(project_root, task_path)
        tasks.append(
            DatasetTaskEntry(
                task_id=task_path,
                task_path=task_path,
                content_hash=content_hash,
                domain="electrical",
                difficulty="medium",
                tags=["test"],
            )
        )

    return DatasetManifest(
        name=name,
        version=version,
        content_hash="abc123def456" * 5 + "abcd",
        description=DatasetDescription(
            summary="Test dataset for porter tests",
            purpose="Verify export/import round-trip",
            domains=["electrical"],
            difficulty_distribution={"medium": len(tasks)},
            task_count=len(tasks),
        ),
        created_at=datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC),
        tasks=tasks,
        source=DatasetSource(method="manual"),
    )


class TestExportDataset:
    def test_creates_tar_gz_file(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        manifest = _make_manifest(project_root)
        output = tmp_path / "out" / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=output)

        assert output.is_file()

    def test_archive_contains_manifest_json(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        manifest = _make_manifest(project_root)
        output = tmp_path / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=output)

        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        assert "manifest.json" in names

    def test_archive_contains_readme(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        manifest = _make_manifest(project_root)
        output = tmp_path / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=output)

        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        assert "README.md" in names

    def test_manifest_json_is_valid(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        manifest = _make_manifest(project_root)
        output = tmp_path / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=output)

        with tarfile.open(output, "r:gz") as tar:
            member = tar.getmember("manifest.json")
            extracted = tar.extractfile(member)
            assert extracted is not None
            data = json.loads(extracted.read().decode("utf-8"))

        assert data["name"] == "test-suite"
        assert data["version"] == "1.0.0"
        assert len(data["tasks"]) == 1

    def test_archive_contains_task_files(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        task_path = "tasks/electrical/voltage-drop/instance-0"
        manifest = _make_manifest(project_root, task_paths=[task_path])
        output = tmp_path / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=output)

        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()

        assert any(task_path in name for name in names)

    def test_readme_contains_dataset_name(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        manifest = _make_manifest(project_root, name="my-dataset")
        output = tmp_path / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=output)

        with tarfile.open(output, "r:gz") as tar:
            member = tar.getmember("README.md")
            extracted = tar.extractfile(member)
            assert extracted is not None
            readme = extracted.read().decode("utf-8")

        assert "my-dataset" in readme

    def test_export_creates_parent_directories(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        manifest = _make_manifest(project_root)
        output = tmp_path / "deeply" / "nested" / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=output)

        assert output.is_file()

    def test_missing_task_dirs_are_skipped_gracefully(self, tmp_path: Path) -> None:
        """Tasks whose directories don't exist are skipped — no error raised."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        # Build manifest with a task whose directory doesn't exist on disk
        tasks = [
            DatasetTaskEntry(
                task_id="tasks/electrical/ghost/instance-0",
                task_path="tasks/electrical/ghost/instance-0",
                content_hash="a" * 64,
                domain="electrical",
                difficulty="medium",
                tags=[],
            )
        ]
        manifest = DatasetManifest(
            name="sparse",
            version="1.0.0",
            content_hash="b" * 64,
            description=DatasetDescription(
                summary="Sparse dataset",
                domains=["electrical"],
                task_count=1,
            ),
            created_at=datetime(2025, 6, 15, tzinfo=UTC),
            tasks=tasks,
            source=DatasetSource(method="manual"),
        )
        output = tmp_path / "archive.tar.gz"

        # Should not raise
        export_dataset(manifest=manifest, project_root=project_root, output_path=output)
        assert output.is_file()


class TestImportDataset:
    def test_round_trip_manifest_matches(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        manifest = _make_manifest(project_root)
        archive = tmp_path / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=archive)

        import_root = tmp_path / "import"
        import_root.mkdir()
        tasks_root = import_root / "tasks"
        datasets_root = import_root / "datasets"

        imported = import_dataset(
            archive_path=archive,
            tasks_root=tasks_root,
            datasets_root=datasets_root,
        )

        assert imported.name == manifest.name
        assert imported.version == manifest.version
        assert imported.content_hash == manifest.content_hash

    def test_round_trip_task_files_extracted(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        task_path = "tasks/electrical/voltage-drop/instance-0"
        manifest = _make_manifest(project_root, task_paths=[task_path])
        archive = tmp_path / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=archive)

        import_root = tmp_path / "import"
        import_root.mkdir()
        tasks_root = import_root / "tasks"
        datasets_root = import_root / "datasets"

        import_dataset(
            archive_path=archive,
            tasks_root=tasks_root,
            datasets_root=datasets_root,
        )

        extracted_instruction = import_root / task_path / "instruction.md"
        assert extracted_instruction.is_file()

    def test_round_trip_registers_manifest(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        manifest = _make_manifest(project_root, name="my-suite", version="2.0.0")
        archive = tmp_path / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=archive)

        import_root = tmp_path / "import"
        import_root.mkdir()
        tasks_root = import_root / "tasks"
        datasets_root = import_root / "datasets"

        import_dataset(
            archive_path=archive,
            tasks_root=tasks_root,
            datasets_root=datasets_root,
        )

        manifest_path = datasets_root / "my-suite" / "2.0.0" / "manifest.json"
        assert manifest_path.is_file()
        stored = read_manifest(manifest_path)
        assert stored.name == "my-suite"
        assert stored.version == "2.0.0"

    def test_import_integrity_check_fails_on_corrupt_task(self, tmp_path: Path) -> None:
        """If a task file is modified after export, import should fail integrity check."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        task_path = "tasks/electrical/voltage-drop/instance-0"
        manifest = _make_manifest(project_root, task_paths=[task_path])
        archive = tmp_path / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=archive)

        # Tamper: open archive, modify a task file, repack
        tampered_archive = tmp_path / "tampered.tar.gz"
        with tarfile.open(archive, "r:gz") as original:
            with tarfile.open(tampered_archive, "w:gz") as tampered:
                for member in original.getmembers():
                    if member.name.endswith("instruction.md"):
                        # Replace with different content
                        import io

                        bad_content = b"TAMPERED CONTENT"
                        member.size = len(bad_content)
                        tampered.addfile(member, io.BytesIO(bad_content))
                    else:
                        extracted = original.extractfile(member)
                        if extracted is not None:
                            tampered.addfile(member, extracted)
                        else:
                            tampered.addfile(member)

        import_root = tmp_path / "import"
        import_root.mkdir()
        tasks_root = import_root / "tasks"
        datasets_root = import_root / "datasets"

        with pytest.raises(ValueError, match="Integrity check failed"):
            import_dataset(
                archive_path=tampered_archive,
                tasks_root=tasks_root,
                datasets_root=datasets_root,
            )

    def test_import_multiple_tasks_round_trip(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        task_paths = [
            "tasks/electrical/voltage-drop/instance-0",
            "tasks/electrical/cable-sizing/instance-0",
            "tasks/civil/pipe-flow/instance-0",
        ]
        manifest = _make_manifest(project_root, task_paths=task_paths)
        archive = tmp_path / "archive.tar.gz"

        export_dataset(manifest=manifest, project_root=project_root, output_path=archive)

        import_root = tmp_path / "import"
        import_root.mkdir()
        tasks_root = import_root / "tasks"
        datasets_root = import_root / "datasets"

        imported = import_dataset(
            archive_path=archive,
            tasks_root=tasks_root,
            datasets_root=datasets_root,
        )

        assert len(imported.tasks) == 3
        for task_path in task_paths:
            extracted_instruction = import_root / task_path / "instruction.md"
            assert extracted_instruction.is_file(), f"Missing: {extracted_instruction}"
