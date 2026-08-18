# ABOUTME: Tests dataset publication and reference resolution across bundle and repository boundaries.
# ABOUTME: Ensures labels remain discovery metadata while execution receives exact references.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aec_bench.contracts.dataset import BundleDatasetRef, DatasetManifest, DatasetTaskEntry
from aec_bench.dataset.publication import publish_dataset, resolve_dataset, verify_resolved_dataset
from aec_bench.dataset.storage import (
    list_publications,
    read_dataset_reference,
    reference_path,
    write_manifest,
)


def _fixture(tmp_path: Path) -> tuple[Path, Path, DatasetManifest]:
    project_root = tmp_path / "project"
    task = project_root / "tasks" / "civil" / "task-a"
    task.mkdir(parents=True)
    (task / "task.toml").write_text('[metadata]\ndifficulty = "medium"\n', encoding="utf-8")
    (task / "instruction.md").write_text("Solve it\n", encoding="utf-8")
    manifest = DatasetManifest(
        dataset_id="core",
        description="Core dataset",
        tasks=[DatasetTaskEntry(task_id="civil/task-a", path="tasks/civil/task-a", task_kind="artifact")],
    )
    datasets_root = project_root / "artefacts" / "datasets"
    write_manifest(datasets_root, manifest)
    return project_root, datasets_root, manifest


def test_bundle_publication_persists_reference_outside_bundle_and_assigns_label(tmp_path: Path) -> None:
    project_root, datasets_root, manifest = _fixture(tmp_path)
    published_at = datetime(2026, 8, 18, tzinfo=UTC)

    publication = publish_dataset(
        manifest=manifest,
        datasets_root=datasets_root,
        project_root=project_root,
        label="public-2026",
        published_at=published_at,
    )

    assert isinstance(publication.dataset_ref, BundleDatasetRef)
    assert publication.published_at == published_at
    assert list_publications(datasets_root) == [publication]
    assert read_dataset_reference(reference_path(datasets_root, publication.dataset_ref)) == publication.dataset_ref


def test_publication_label_cannot_be_implicitly_reassigned(tmp_path: Path) -> None:
    project_root, datasets_root, manifest = _fixture(tmp_path)
    publish_dataset(
        manifest=manifest,
        datasets_root=datasets_root,
        project_root=project_root,
        label="public-2026",
    )

    with pytest.raises(FileExistsError, match="already exists"):
        publish_dataset(
            manifest=manifest,
            datasets_root=datasets_root,
            project_root=project_root,
            label="public-2026",
        )


def test_selector_resolution_returns_manifest_and_exact_reference(tmp_path: Path) -> None:
    project_root, datasets_root, manifest = _fixture(tmp_path)
    publication = publish_dataset(
        manifest=manifest,
        datasets_root=datasets_root,
        project_root=project_root,
        label="public-2026",
    )

    resolved = resolve_dataset(
        datasets_root=datasets_root,
        selector="core@public-2026",
        project_root=project_root,
    )

    assert resolved is not None
    assert resolved.reference == publication.dataset_ref
    assert resolved.manifest == manifest
    assert verify_resolved_dataset(resolved, datasets_root=datasets_root, project_root=project_root).is_clean


def test_modified_materialisation_fails_integrity_after_reference_resolution(tmp_path: Path) -> None:
    project_root, datasets_root, manifest = _fixture(tmp_path)
    publication = publish_dataset(
        manifest=manifest,
        datasets_root=datasets_root,
        project_root=project_root,
        label="public-2026",
    )
    resolved = resolve_dataset(
        datasets_root=datasets_root,
        selector=publication.dataset_ref,
        project_root=project_root,
    )
    assert resolved is not None
    (project_root / "tasks/civil/task-a/instruction.md").write_text("changed\n", encoding="utf-8")

    integrity = verify_resolved_dataset(resolved, datasets_root=datasets_root, project_root=project_root)

    assert not integrity.is_clean
    assert integrity.modified == ("civil/task-a",)
