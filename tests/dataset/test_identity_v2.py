# ABOUTME: Specifies the immutable dataset manifest, reference, and publication boundaries.
# ABOUTME: Prevents mutable labels and redundant hashes from becoming execution identity.

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.dataset import (
    BundleDatasetRef,
    DatasetGeneration,
    DatasetManifest,
    DatasetPublication,
    DatasetTaskEntry,
    RepositoryDatasetRef,
    dataset_reference_key,
)


def _manifest() -> DatasetManifest:
    return DatasetManifest(
        dataset_id="worlds-core",
        description="Core benchmark tasks",
        tasks=[
            DatasetTaskEntry(
                task_id="civil/pump-world-001",
                path="tasks/civil/pump-world-001",
                task_kind="world",
            )
        ],
        generation=DatasetGeneration(seed=42, config_ref="suite.toml"),
    )


def test_manifest_has_one_minimal_schema_two_shape() -> None:
    payload = _manifest().model_dump(mode="json")

    assert payload == {
        "schema_version": 2,
        "dataset_id": "worlds-core",
        "description": "Core benchmark tasks",
        "tasks": [
            {
                "task_id": "civil/pump-world-001",
                "path": "tasks/civil/pump-world-001",
                "task_kind": "world",
            }
        ],
        "generation": {"seed": 42, "config_ref": "suite.toml"},
    }
    assert not ({"version", "content_hash", "created_at", "template_versions"} & payload.keys())
    assert "content_hash" not in payload["tasks"][0]


def test_manifest_rejects_duplicate_task_ids_and_paths() -> None:
    first = DatasetTaskEntry(task_id="task-a", path="tasks/a", task_kind="artifact")

    with pytest.raises(ValidationError, match="task_id values must be unique"):
        DatasetManifest(dataset_id="dupes", description="Duplicate IDs", tasks=[first, first])

    with pytest.raises(ValidationError, match="task paths must be unique"):
        DatasetManifest(
            dataset_id="dupe-paths",
            description="Duplicate paths",
            tasks=[first, DatasetTaskEntry(task_id="task-b", path="tasks/a", task_kind="artifact")],
        )


@pytest.mark.parametrize("path", ["/absolute/task", "../outside", "tasks/../outside", "tasks\\outside"])
def test_dataset_paths_must_be_portable_and_relative(path: str) -> None:
    with pytest.raises(ValidationError, match="relative|portable"):
        DatasetTaskEntry(task_id="task-a", path=path, task_kind="artifact")


def test_repository_reference_requires_a_full_git_commit() -> None:
    ref = RepositoryDatasetRef(
        dataset_id="worlds-core",
        source_revision="a" * 40,
        manifest_path="datasets/worlds-core/manifest.json",
    )

    assert ref.kind == "repository"
    assert dataset_reference_key(ref) == (
        "repository:worlds-core@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:datasets/worlds-core/manifest.json"
    )

    with pytest.raises(ValidationError, match="40-character"):
        RepositoryDatasetRef(
            dataset_id="worlds-core",
            source_revision="abc123",
            manifest_path="datasets/worlds-core/manifest.json",
        )


def test_bundle_reference_uses_one_external_artifact_reference() -> None:
    ref = BundleDatasetRef(
        dataset_id="worlds-core",
        artifact=ArtifactRef(
            artifact_id=f"artifacts/sha256/aa/{'a' * 64}",
            sha256="a" * 64,
            size_bytes=123,
            media_type="application/vnd.aec-bench.dataset-bundle+tar+gzip",
        ),
    )

    assert ref.kind == "bundle"
    assert dataset_reference_key(ref) == f"bundle:worlds-core@{'a' * 64}"


def test_publication_time_and_label_are_outside_dataset_content() -> None:
    ref = RepositoryDatasetRef(
        dataset_id="worlds-core",
        source_revision="b" * 40,
        manifest_path="datasets/worlds-core/manifest.json",
    )
    publication = DatasetPublication(
        dataset_ref=ref,
        label="public-2026",
        published_at=datetime(2026, 8, 18, tzinfo=UTC),
    )

    assert publication.label == "public-2026"
    assert "published_at" not in _manifest().model_dump(mode="json")


def test_latest_is_not_a_valid_persisted_publication_label() -> None:
    ref = RepositoryDatasetRef(
        dataset_id="worlds-core",
        source_revision="c" * 40,
        manifest_path="datasets/worlds-core/manifest.json",
    )

    with pytest.raises(ValidationError, match="latest"):
        DatasetPublication(
            dataset_ref=ref,
            label="latest",
            published_at=datetime(2026, 8, 18, tzinfo=UTC),
        )
