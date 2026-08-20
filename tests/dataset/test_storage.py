# ABOUTME: Tests immutable dataset manifest and publication-label storage.
# ABOUTME: Proves interactive selectors resolve to exact references before execution.

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from aec_bench.contracts.dataset import (
    DatasetManifest,
    DatasetPublication,
    DatasetTaskEntry,
    RepositoryDatasetRef,
)
from aec_bench.dataset.storage import (
    list_datasets,
    list_publications,
    manifest_path,
    read_manifest,
    resolve_dataset_reference,
    save_dataset,
    write_publication,
)


def _manifest(dataset_id: str = "test-suite", task_count: int = 1) -> DatasetManifest:
    return DatasetManifest(
        dataset_id=dataset_id,
        description="Test dataset",
        tasks=[
            DatasetTaskEntry(
                task_id=f"task-{index}",
                path=f"tasks/task-{index}",
                task_kind="artifact",
            )
            for index in range(task_count)
        ],
    )


def _publication(
    dataset_id: str = "test-suite",
    label: str = "public-2026",
    *,
    revision: str = "a" * 40,
    published_at: datetime | None = None,
) -> DatasetPublication:
    return DatasetPublication(
        dataset_ref=RepositoryDatasetRef(
            dataset_id=dataset_id,
            source_revision=revision,
            manifest_path=f"datasets/{dataset_id}/manifest.json",
        ),
        label=label,
        published_at=published_at or datetime(2026, 8, 18, tzinfo=UTC),
    )


def test_manifest_storage_uses_one_dataset_id_path_and_canonical_bytes(tmp_path: Path) -> None:
    stored = save_dataset(tmp_path, _manifest())

    assert stored == tmp_path / "manifests" / "test-suite" / "manifest.json"
    assert stored.read_bytes().endswith(b"\n")
    assert json.loads(stored.read_bytes()) == _manifest().model_dump(mode="json")
    assert read_manifest(stored) == _manifest()


def test_manifest_publication_is_immutable(tmp_path: Path) -> None:
    save_dataset(tmp_path, _manifest())

    with pytest.raises(FileExistsError, match="already exists"):
        save_dataset(tmp_path, _manifest(task_count=2))


def test_manifest_path_rejects_path_like_dataset_ids(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="dataset_id"):
        manifest_path(tmp_path, "../outside")


def test_list_datasets_returns_only_schema_two_manifests(tmp_path: Path) -> None:
    save_dataset(tmp_path, _manifest("beta"))
    save_dataset(tmp_path, _manifest("alpha"))
    (tmp_path / "other" / "old" / "1.0.0").mkdir(parents=True)
    (tmp_path / "other" / "old" / "1.0.0" / "manifest.json").write_text("{}", encoding="utf-8")

    assert [manifest.dataset_id for manifest in list_datasets(tmp_path)] == ["alpha", "beta"]


def test_publication_labels_are_immutable_records(tmp_path: Path) -> None:
    publication = _publication()
    path = write_publication(tmp_path, publication)

    assert path == tmp_path / "publications" / "test-suite" / "public-2026.json"
    assert list_publications(tmp_path, dataset_id="test-suite") == [publication]
    with pytest.raises(FileExistsError, match="already exists"):
        write_publication(tmp_path, _publication(revision="b" * 40))


def test_exact_label_resolves_to_immutable_reference(tmp_path: Path) -> None:
    publication = _publication()
    write_publication(tmp_path, publication)

    assert resolve_dataset_reference(tmp_path, "test-suite@public-2026") == publication.dataset_ref


def test_plain_dataset_id_resolves_latest_publication_event_before_persistence(tmp_path: Path) -> None:
    first = _publication(label="candidate", revision="a" * 40)
    second = _publication(
        label="public-2026",
        revision="b" * 40,
        published_at=first.published_at + timedelta(seconds=1),
    )
    write_publication(tmp_path, first)
    write_publication(tmp_path, second)

    assert resolve_dataset_reference(tmp_path, "test-suite") == second.dataset_ref


def test_latest_selector_is_rejected_instead_of_becoming_persisted_identity(tmp_path: Path) -> None:
    write_publication(tmp_path, _publication())

    with pytest.raises(ValueError, match="latest"):
        resolve_dataset_reference(tmp_path, "test-suite@latest")


def test_unpublished_manifest_does_not_resolve_for_execution(tmp_path: Path) -> None:
    save_dataset(tmp_path, _manifest())

    assert resolve_dataset_reference(tmp_path, "test-suite") is None
