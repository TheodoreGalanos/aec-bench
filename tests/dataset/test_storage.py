# ABOUTME: Tests for dataset manifest storage — write, read, list, and resolve operations.
# ABOUTME: Uses tmp_path fixtures to verify filesystem-backed manifest persistence.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aec_bench.contracts.dataset import (
    DatasetDescription,
    DatasetManifest,
    DatasetSource,
    DatasetTaskEntry,
)
from aec_bench.dataset.storage import (
    list_datasets,
    read_manifest,
    resolve_dataset,
    write_manifest,
)


def _make_manifest(
    name: str = "test-suite",
    version: str = "1.0.0",
    task_count: int = 1,
) -> DatasetManifest:
    """Build a minimal valid manifest for testing."""
    tasks = [
        DatasetTaskEntry(
            task_id=f"electrical/voltage-drop/instance-{i}",
            task_path=f"electrical/voltage-drop/instance-{i}",
            content_hash=f"sha256-{'a' * 60}{i:04d}",
            domain="electrical",
            difficulty="medium",
            tags=["voltage-drop"],
        )
        for i in range(task_count)
    ]
    return DatasetManifest(
        name=name,
        version=version,
        content_hash="abc123def456" * 5 + "abcd",
        description=DatasetDescription(
            summary="Test dataset for unit tests",
            purpose="Verify storage round-trip",
            domains=["electrical"],
            difficulty_distribution={"medium": task_count},
            task_count=task_count,
        ),
        created_at=datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC),
        tasks=tasks,
        source=DatasetSource(method="manual"),
    )


class TestWriteManifest:
    def test_writes_manifest_to_correct_path(self, tmp_path: Path) -> None:
        manifest = _make_manifest(name="my-suite", version="1.0.0")
        result_path = write_manifest(tmp_path, manifest)

        expected = tmp_path / "my-suite" / "1.0.0" / "manifest.json"
        assert result_path == expected
        assert result_path.is_file()

    def test_written_manifest_is_valid_json(self, tmp_path: Path) -> None:
        manifest = _make_manifest()
        result_path = write_manifest(tmp_path, manifest)

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["name"] == "test-suite"
        assert data["version"] == "1.0.0"
        assert len(data["tasks"]) == 1

    def test_raises_file_exists_error_without_overwrite(self, tmp_path: Path) -> None:
        manifest = _make_manifest()
        write_manifest(tmp_path, manifest)

        with pytest.raises(FileExistsError, match="already exists"):
            write_manifest(tmp_path, manifest)

    def test_overwrite_replaces_existing(self, tmp_path: Path) -> None:
        manifest_v1 = _make_manifest(task_count=1)
        write_manifest(tmp_path, manifest_v1)

        manifest_v2 = _make_manifest(task_count=2)
        result_path = write_manifest(tmp_path, manifest_v2, overwrite=True)

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert len(data["tasks"]) == 2

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        deep_root = tmp_path / "artefacts" / "datasets"
        manifest = _make_manifest()
        result_path = write_manifest(deep_root, manifest)

        assert result_path.is_file()


class TestReadManifest:
    def test_round_trip(self, tmp_path: Path) -> None:
        original = _make_manifest()
        result_path = write_manifest(tmp_path, original)

        loaded = read_manifest(result_path)
        assert loaded.name == original.name
        assert loaded.version == original.version
        assert loaded.content_hash == original.content_hash
        assert len(loaded.tasks) == len(original.tasks)

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "no-such" / "manifest.json"
        with pytest.raises(FileNotFoundError):
            read_manifest(missing)

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not-json", encoding="utf-8")
        with pytest.raises(Exception):  # noqa: B017
            read_manifest(bad_file)


class TestListDatasets:
    def test_empty_root(self, tmp_path: Path) -> None:
        result = list_datasets(tmp_path)
        assert result == []

    def test_finds_all_manifests(self, tmp_path: Path) -> None:
        write_manifest(tmp_path, _make_manifest(name="alpha", version="1.0.0"))
        write_manifest(tmp_path, _make_manifest(name="alpha", version="2.0.0"))
        write_manifest(tmp_path, _make_manifest(name="beta", version="1.0.0"))

        result = list_datasets(tmp_path)
        assert len(result) == 3

    def test_returns_valid_manifests(self, tmp_path: Path) -> None:
        write_manifest(tmp_path, _make_manifest(name="suite", version="1.0.0"))
        result = list_datasets(tmp_path)
        assert all(isinstance(m, DatasetManifest) for m in result)

    def test_skips_non_manifest_directories(self, tmp_path: Path) -> None:
        (tmp_path / "random-dir").mkdir()
        (tmp_path / "random-dir" / "notes.txt").write_text("not a manifest")
        result = list_datasets(tmp_path)
        assert result == []

    def test_nonexistent_root_returns_empty(self, tmp_path: Path) -> None:
        missing_root = tmp_path / "does-not-exist"
        result = list_datasets(missing_root)
        assert result == []


class TestResolveDataset:
    def test_resolve_by_name_returns_latest_version(self, tmp_path: Path) -> None:
        write_manifest(tmp_path, _make_manifest(name="suite", version="1.0.0"))
        write_manifest(tmp_path, _make_manifest(name="suite", version="2.0.0"))
        write_manifest(tmp_path, _make_manifest(name="suite", version="1.1.0"))

        result = resolve_dataset(tmp_path, "suite")
        assert result is not None
        assert result.version == "2.0.0"

    def test_resolve_by_name_at_version(self, tmp_path: Path) -> None:
        write_manifest(tmp_path, _make_manifest(name="suite", version="1.0.0"))
        write_manifest(tmp_path, _make_manifest(name="suite", version="2.0.0"))

        result = resolve_dataset(tmp_path, "suite@1.0.0")
        assert result is not None
        assert result.version == "1.0.0"

    def test_resolve_missing_dataset_returns_none(self, tmp_path: Path) -> None:
        result = resolve_dataset(tmp_path, "nonexistent")
        assert result is None

    def test_resolve_missing_version_returns_none(self, tmp_path: Path) -> None:
        write_manifest(tmp_path, _make_manifest(name="suite", version="1.0.0"))
        result = resolve_dataset(tmp_path, "suite@9.9.9")
        assert result is None

    def test_semver_sorting_not_lexicographic(self, tmp_path: Path) -> None:
        """Version 10.0.0 should sort higher than 2.0.0 (not lexicographically)."""
        write_manifest(tmp_path, _make_manifest(name="suite", version="2.0.0"))
        write_manifest(tmp_path, _make_manifest(name="suite", version="10.0.0"))
        write_manifest(tmp_path, _make_manifest(name="suite", version="1.0.0"))

        result = resolve_dataset(tmp_path, "suite")
        assert result is not None
        assert result.version == "10.0.0"
