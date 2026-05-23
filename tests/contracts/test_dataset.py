# ABOUTME: Tests for Dataset contract models — manifest, description, task entries, source.
# ABOUTME: Pure model validation tests with no I/O.

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aec_bench.contracts.dataset import (
    DatasetDescription,
    DatasetManifest,
    DatasetSource,
    DatasetTaskEntry,
)


def test_dataset_task_entry_basic() -> None:
    entry = DatasetTaskEntry(
        task_id="electrical/voltage-drop",
        task_path="tasks/electrical/voltage-drop",
        content_hash="abc123",
        domain="electrical",
        difficulty="easy",
    )
    assert entry.task_id == "electrical/voltage-drop"
    assert entry.tags == []


def test_dataset_task_entry_with_tags() -> None:
    entry = DatasetTaskEntry(
        task_id="civil/rational-method",
        task_path="tasks/civil/rational-method",
        content_hash="def456",
        domain="civil",
        difficulty="medium",
        tags=["drainage", "AS-2200"],
    )
    assert len(entry.tags) == 2


def test_dataset_description_basic() -> None:
    desc = DatasetDescription(
        summary="50 tasks across 2 domains",
        domains=["electrical", "civil"],
        standards=["AS/NZS 3008"],
        difficulty_distribution={"easy": 20, "medium": 20, "hard": 10},
        template_count=5,
        task_count=50,
    )
    assert desc.task_count == 50
    assert desc.purpose is None


def test_dataset_source_with_suite_config() -> None:
    source = DatasetSource(
        method="suite_config",
        suite_config={"dataset": [{"template": "voltage-drop", "count": 5}]},
        seed=42,
    )
    assert source.method == "suite_config"
    assert source.seed == 42


def test_dataset_source_invalid_method_rejected() -> None:
    with pytest.raises(ValidationError):
        DatasetSource(method="unknown_method")


def test_dataset_manifest_basic() -> None:
    manifest = DatasetManifest(
        name="test-dataset",
        version="1.0.0",
        content_hash="deadbeef",
        description=DatasetDescription(
            summary="Test",
            domains=["electrical"],
            standards=[],
            difficulty_distribution={"easy": 1},
            template_count=1,
            task_count=1,
        ),
        created_at=datetime.now(UTC),
        tasks=[
            DatasetTaskEntry(
                task_id="electrical/voltage-drop",
                task_path="tasks/electrical/voltage-drop",
                content_hash="abc123",
                domain="electrical",
                difficulty="easy",
            )
        ],
        source=DatasetSource(method="manual"),
    )
    assert manifest.name == "test-dataset"
    assert len(manifest.tasks) == 1


def test_dataset_manifest_rejects_empty_tasks() -> None:
    with pytest.raises(Exception, match="tasks"):
        DatasetManifest(
            name="empty",
            version="1.0.0",
            content_hash="deadbeef",
            description=DatasetDescription(
                summary="Empty",
                domains=[],
                standards=[],
                difficulty_distribution={},
                template_count=0,
                task_count=0,
            ),
            created_at=datetime.now(UTC),
            tasks=[],
            source=DatasetSource(method="manual"),
        )


def test_dataset_manifest_rejects_duplicate_task_ids() -> None:
    entry = DatasetTaskEntry(
        task_id="electrical/voltage-drop",
        task_path="tasks/electrical/voltage-drop",
        content_hash="abc123",
        domain="electrical",
        difficulty="easy",
    )
    with pytest.raises(Exception, match="unique"):
        DatasetManifest(
            name="dupes",
            version="1.0.0",
            content_hash="deadbeef",
            description=DatasetDescription(
                summary="Dupes",
                domains=["electrical"],
                standards=[],
                difficulty_distribution={"easy": 2},
                template_count=1,
                task_count=2,
            ),
            created_at=datetime.now(UTC),
            tasks=[entry, entry],
            source=DatasetSource(method="manual"),
        )
