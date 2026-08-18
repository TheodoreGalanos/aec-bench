# ABOUTME: Tests the bounded v1 dataset migration reader and its verification states.
# ABOUTME: Ensures partial or invalid legacy data cannot become an immutable publication.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aec_bench.dataset.hashing import hash_task_directory
from aec_bench.dataset.legacy import LegacyMigrationStatus, inspect_v1_manifest, migrate_v1_dataset


def _legacy_fixture(tmp_path: Path) -> tuple[Path, Path]:
    project_root = tmp_path / "project"
    task = project_root / "tasks" / "civil" / "task-a"
    (task / "tests").mkdir(parents=True)
    (task / "task.toml").write_text('[metadata]\ndifficulty = "medium"\n', encoding="utf-8")
    (task / "instruction.md").write_text("Solve it\n", encoding="utf-8")
    (task / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    task_hash = hash_task_directory(task)
    top_level_hash = hashlib.sha256(f"civil/task-a:{task_hash}".encode()).hexdigest()
    payload = {
        "name": "legacy-core",
        "version": "1.0.0",
        "content_hash": top_level_hash,
        "description": {
            "summary": "Legacy core dataset",
            "purpose": None,
            "standards": [],
            "domains": ["civil"],
            "difficulty_distribution": {"medium": 1},
            "template_count": 0,
            "task_count": 1,
        },
        "created_at": "2026-01-01T00:00:00Z",
        "tasks": [
            {
                "task_id": "civil/task-a",
                "task_path": "tasks/civil/task-a",
                "content_hash": task_hash,
                "domain": "civil",
                "difficulty": "medium",
                "tags": [],
            }
        ],
        "source": {"method": "manual", "suite_config": None, "seed": None, "template_versions": {}},
    }
    manifest_path = project_root / "legacy-manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    return project_root, manifest_path


def test_v1_manifest_is_fully_verified_before_conversion(tmp_path: Path) -> None:
    project_root, manifest_path = _legacy_fixture(tmp_path)

    result = inspect_v1_manifest(manifest_path, project_root=project_root)

    assert result.status is LegacyMigrationStatus.FULLY_VERIFIED
    assert result.manifest is not None
    assert result.manifest.dataset_id == "legacy-core"
    assert result.manifest.schema_version == 2
    assert result.manifest.tasks[0].path == "tasks/civil/task-a"
    assert "content_hash" not in result.manifest.model_dump(mode="json")


def test_v1_manifest_without_task_bytes_is_explicitly_partial(tmp_path: Path) -> None:
    _, manifest_path = _legacy_fixture(tmp_path)

    result = inspect_v1_manifest(manifest_path)

    assert result.status is LegacyMigrationStatus.PARTIALLY_VERIFIED
    assert result.manifest is None
    assert result.issues == ("task bytes were not supplied for v1 hash verification",)


def test_v1_manifest_with_wrong_top_level_hash_is_invalid(tmp_path: Path) -> None:
    project_root, manifest_path = _legacy_fixture(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["content_hash"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    result = inspect_v1_manifest(manifest_path, project_root=project_root)

    assert result.status is LegacyMigrationStatus.INVALID
    assert result.manifest is None
    assert "top-level content_hash mismatch" in result.issues


def test_v1_manifest_with_missing_or_modified_task_is_invalid(tmp_path: Path) -> None:
    project_root, manifest_path = _legacy_fixture(tmp_path)
    (project_root / "tasks/civil/task-a/instruction.md").write_text("changed\n", encoding="utf-8")

    result = inspect_v1_manifest(manifest_path, project_root=project_root)

    assert result.status is LegacyMigrationStatus.INVALID
    assert result.manifest is None
    assert result.issues == ("task hash mismatch: civil/task-a",)


def test_v1_manifest_rejects_unsafe_task_paths(tmp_path: Path) -> None:
    project_root, manifest_path = _legacy_fixture(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["tasks"][0]["task_path"] = "../outside"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    result = inspect_v1_manifest(manifest_path, project_root=project_root)

    assert result.status is LegacyMigrationStatus.INVALID
    assert result.manifest is None
    assert any("portable relative path" in issue for issue in result.issues)


def test_only_fully_verified_v1_manifest_can_be_republished(tmp_path: Path) -> None:
    project_root, manifest_path = _legacy_fixture(tmp_path)
    datasets_root = project_root / "datasets"

    publication = migrate_v1_dataset(
        manifest_path,
        project_root=project_root,
        datasets_root=datasets_root,
        label="migrated-2026",
    )

    assert publication.dataset_ref.kind == "bundle"
    assert (datasets_root / "manifests" / "legacy-core" / "manifest.json").is_file()


def test_partial_v1_manifest_cannot_be_republished(tmp_path: Path) -> None:
    _, manifest_path = _legacy_fixture(tmp_path)

    with pytest.raises(ValueError, match="fully verified"):
        migrate_v1_dataset(
            manifest_path,
            project_root=None,
            datasets_root=tmp_path / "datasets",
            label="bad-migration",
        )
