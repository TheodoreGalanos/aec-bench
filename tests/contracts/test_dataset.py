# ABOUTME: Tests the schema-2 dataset contract and its exact reference variants.
# ABOUTME: Ensures semantic content, source identity, and publication metadata stay separate.

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.dataset import (
    BundleDatasetRef,
    DatasetManifest,
    DatasetPublication,
    DatasetTaskEntry,
    RepositoryDatasetRef,
)


def _task(task_id: str = "electrical/voltage-drop") -> DatasetTaskEntry:
    return DatasetTaskEntry(task_id=task_id, path=f"tasks/{task_id}", task_kind="artifact")


def test_manifest_contains_semantic_selection_only() -> None:
    manifest = DatasetManifest(dataset_id="core", description="Core tasks", tasks=[_task()])

    assert manifest.model_dump(mode="json") == {
        "schema_version": 2,
        "dataset_id": "core",
        "description": "Core tasks",
        "tasks": [
            {
                "task_id": "electrical/voltage-drop",
                "path": "tasks/electrical/voltage-drop",
                "task_kind": "artifact",
            }
        ],
        "generation": None,
    }


def test_manifest_rejects_duplicate_task_ids() -> None:
    with pytest.raises(ValidationError, match="task_id values must be unique"):
        DatasetManifest(
            dataset_id="core",
            description="Core tasks",
            tasks=[_task(), DatasetTaskEntry(task_id=_task().task_id, path="tasks/other", task_kind="artifact")],
        )


def test_repository_reference_requires_full_git_commit() -> None:
    with pytest.raises(ValidationError, match="40-character Git commit"):
        RepositoryDatasetRef(
            dataset_id="core",
            source_revision="abc123",
            manifest_path="datasets/core/manifest.json",
        )


def test_bundle_reference_uses_one_enclosing_artifact() -> None:
    reference = BundleDatasetRef(
        dataset_id="core",
        artifact=ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            sha256="a" * 64,
            size_bytes=42,
            media_type="application/vnd.aec-bench.dataset-bundle+tar+gzip",
        ),
    )

    assert reference.kind == "bundle"
    assert reference.artifact.sha256 == "a" * 64


def test_publication_time_requires_timezone() -> None:
    reference = RepositoryDatasetRef(
        dataset_id="core",
        source_revision="a" * 40,
        manifest_path="datasets/core/manifest.json",
    )

    with pytest.raises(ValidationError, match="timezone"):
        DatasetPublication(dataset_ref=reference, label="public-2026", published_at=datetime(2026, 1, 1))

    publication = DatasetPublication(
        dataset_ref=reference,
        label="public-2026",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert publication.label == "public-2026"
