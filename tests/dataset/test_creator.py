# ABOUTME: Tests schema-2 dataset creation from validated task definitions.
# ABOUTME: Ensures missing tasks fail and new writes contain no layered content identity.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.contracts.dataset import DatasetGeneration, DatasetManifest
from aec_bench.contracts.task_definition import Difficulty
from aec_bench.dataset.creator import compose_dataset
from aec_bench.dataset.storage import read_manifest, save_dataset
from tests.support.task_factories import make_task_definition


def _create_task_on_disk(tasks_root: Path, task_id: str) -> None:
    task_dir = tasks_root / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.toml").write_text('[metadata]\ndifficulty = "medium"\n', encoding="utf-8")
    (task_dir / "instruction.md").write_text(f"# Task {task_id}\n", encoding="utf-8")


def test_create_writes_one_minimal_manifest(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = "electrical/voltage-drop/instance-001"
    _create_task_on_disk(tasks_root, task_id)

    manifest = compose_dataset(
        dataset_id="test-suite",
        tasks=[make_task_definition(task_id=task_id, domain="electrical", difficulty=Difficulty.MEDIUM)],
        tasks_root=tasks_root,
        description="Test dataset",
        generation=DatasetGeneration(seed=42, config_ref="suite.toml"),
    )
    save_dataset(tmp_path / "datasets", manifest)

    assert isinstance(manifest, DatasetManifest)
    assert manifest.dataset_id == "test-suite"
    assert manifest.tasks[0].path == f"tasks/{task_id}"
    assert manifest.tasks[0].task_kind == "artifact"
    stored = read_manifest(tmp_path / "datasets" / "manifests" / "test-suite" / "manifest.json")
    assert stored == manifest
    payload = stored.model_dump(mode="json")
    assert "version" not in payload
    assert "content_hash" not in payload
    assert "created_at" not in payload


def test_create_orders_tasks_by_stable_task_id(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    for task_id in ("mechanical/task-b", "civil/task-a"):
        _create_task_on_disk(tasks_root, task_id)

    manifest = compose_dataset(
        dataset_id="ordered",
        tasks=[
            make_task_definition(task_id="mechanical/task-b", domain="mechanical"),
            make_task_definition(task_id="civil/task-a", domain="civil"),
        ],
        tasks_root=tasks_root,
        description="Ordered tasks",
    )

    assert [task.task_id for task in manifest.tasks] == ["civil/task-a", "mechanical/task-b"]


def test_create_uses_explicit_task_kind_metadata(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = "civil/pump-world"
    _create_task_on_disk(tasks_root, task_id)

    manifest = compose_dataset(
        dataset_id="worlds",
        tasks=[make_task_definition(task_id=task_id, domain="civil", metadata={"task_kind": "world"})],
        tasks_root=tasks_root,
        description="World tasks",
    )

    assert manifest.tasks[0].task_kind == "world"


def test_create_fails_when_any_selected_task_directory_is_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="selected task directory is missing"):
        compose_dataset(
            dataset_id="incomplete",
            tasks=[make_task_definition(task_id="civil/missing", domain="civil")],
            tasks_root=tmp_path / "tasks",
            description="Must fail",
        )


def test_create_cannot_overwrite_an_existing_dataset_id(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = "civil/task-a"
    _create_task_on_disk(tasks_root, task_id)
    task = make_task_definition(task_id=task_id, domain="civil")
    kwargs = {
        "dataset_id": "immutable",
        "tasks": [task],
        "tasks_root": tasks_root,
        "description": "Immutable dataset",
    }
    manifest = compose_dataset(**kwargs)
    save_dataset(tmp_path / "datasets", manifest)

    with pytest.raises(FileExistsError, match="already exists"):
        save_dataset(tmp_path / "datasets", manifest)


def test_create_rejects_unknown_task_kind_instead_of_inventing_one(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = "civil/task-a"
    _create_task_on_disk(tasks_root, task_id)

    with pytest.raises(ValueError, match="task_kind"):
        compose_dataset(
            dataset_id="bad-kind",
            tasks=[make_task_definition(task_id=task_id, domain="civil", metadata={"task_kind": "mystery"})],
            tasks_root=tasks_root,
            description="Bad kind",
        )
