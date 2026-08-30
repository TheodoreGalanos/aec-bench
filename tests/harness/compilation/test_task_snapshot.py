# ABOUTME: Tests exact Git-or-artifact task references and separated review data.
# ABOUTME: Verifies deterministic detached archives, path safety, ordering, and stage graphs.

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.contracts.task_review_snapshot import ReviewSnapshot
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef
from aec_bench.harness.compilation.task_snapshot import (
    TaskSnapshotError,
    build_task_snapshot,
    resolve_task_material,
    resolve_task_snapshots,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.tasks.loader import load_task_definition
from aec_bench.tasks.snapshot import read_task_snapshot_archive


def test_detached_task_snapshot_binds_one_exact_archive(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/example")
    repository = ArtifactRepository(tmp_path / "artifacts")
    task = load_task_definition(task_dir, tasks_root)

    first = build_task_snapshot(task=task, tasks_root=tasks_root, artifact_repository=repository)
    second = build_task_snapshot(task=task, tasks_root=tasks_root, artifact_repository=repository)

    assert isinstance(first, ArtifactTaskSnapshotRef)
    assert first == second
    assert first.task_id == task.task_id
    assert (
        read_task_snapshot_archive(repository.read_bytes(first.artifact))["environment/data.json"] == b'{"value": 1}\n'
    )

    (task_dir / "environment" / "data.json").write_text('{"value": 2}\n', encoding="utf-8")
    changed = build_task_snapshot(
        task=load_task_definition(task_dir, tasks_root),
        tasks_root=tasks_root,
        artifact_repository=repository,
    )
    assert changed != first


def test_review_data_is_separate_from_task_identity(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/staged")
    review_payload: dict[str, Any] = {
        "profile_id": "aec.task-review.civil.staged",
        "name": "Staged civil review",
        "task_unit": "generated-task-instance",
        "logic_profile": {"agentic_review": {"required": True}},
        "stages": [
            {"id": "inventory", "produces": ["source_inventory"]},
            {"id": "decision", "consumes": ["source_inventory"], "produces": ["decision"]},
        ],
        "handoffs": [
            {
                "id": "packet_id",
                "producer_stage": "inventory",
                "consumer_stages": ["decision"],
            }
        ],
    }
    (task_dir / "task-review.json").write_text(json.dumps(review_payload, indent=2) + "\n", encoding="utf-8")
    material = resolve_task_material(
        task_refs=("civil/calculation/staged",),
        tasks_root=tasks_root,
        artifact_repository=ArtifactRepository(tmp_path / "artifacts"),
    )

    assert isinstance(material.references[0], ArtifactTaskSnapshotRef)
    assert isinstance(material.review, ReviewSnapshot)
    task_review = material.review.tasks[0]
    assert task_review.profile_id == "aec.task-review.civil.staged"
    assert task_review.visibility.value == "public"
    assert task_review.stage_graph is not None
    assert task_review.stage_graph.topological_order == ("inventory", "decision")
    assert "review" not in material.references[0].model_dump(mode="json")


def test_detached_task_snapshot_binds_executable_file_mode(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/example")
    repository = ArtifactRepository(tmp_path / "artifacts")
    task = load_task_definition(task_dir, tasks_root)
    script = task_dir / "tests" / "test.sh"

    script.chmod(0o644)
    non_executable = build_task_snapshot(task=task, tasks_root=tasks_root, artifact_repository=repository)
    script.chmod(0o755)
    executable = build_task_snapshot(task=task, tasks_root=tasks_root, artifact_repository=repository)

    assert non_executable != executable


def test_detached_task_snapshot_ignores_runtime_cache_files(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/example")
    repository = ArtifactRepository(tmp_path / "artifacts")
    task = load_task_definition(task_dir, tasks_root)
    before = build_task_snapshot(task=task, tasks_root=tasks_root, artifact_repository=repository)

    cache = task_dir / "environment" / "__pycache__"
    cache.mkdir()
    (cache / "tool.cpython-313.pyc").write_bytes(b"transient")
    (task_dir / ".DS_Store").write_bytes(b"transient")

    assert build_task_snapshot(task=task, tasks_root=tasks_root, artifact_repository=repository) == before


def test_detached_task_snapshot_rejects_definition_drift_and_symlinks(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/example")
    repository = ArtifactRepository(tmp_path / "artifacts")
    task = load_task_definition(task_dir, tasks_root)
    (task_dir / "instruction.md").write_text("Changed after the task was loaded.\n", encoding="utf-8")

    with pytest.raises(TaskSnapshotError, match="definition changed"):
        build_task_snapshot(task=task, tasks_root=tasks_root, artifact_repository=repository)

    current = load_task_definition(task_dir, tasks_root)
    target = tmp_path / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    os.symlink(target, task_dir / "environment" / "outside-link")
    with pytest.raises(ValueError, match="symbolic links"):
        build_task_snapshot(task=current, tasks_root=tasks_root, artifact_repository=repository)


def test_resolve_task_snapshots_preserves_requested_order(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "civil/calculation/alpha")
    _write_task(tasks_root, "civil/calculation/beta")
    repository = ArtifactRepository(tmp_path / "artifacts")

    snapshots = resolve_task_snapshots(
        task_refs=("civil/calculation/beta", "civil/calculation/alpha"),
        tasks_root=tasks_root,
        artifact_repository=repository,
    )

    assert tuple(snapshot.task_id for snapshot in snapshots) == (
        "civil/calculation/beta",
        "civil/calculation/alpha",
    )
    with pytest.raises(TaskSnapshotError, match="unknown task refs"):
        resolve_task_snapshots(
            task_refs=("civil/calculation/missing",),
            tasks_root=tasks_root,
            artifact_repository=repository,
        )


def _write_task(tasks_root: Path, task_id: str) -> Path:
    task_dir = tasks_root / task_id
    identity_id = new_entity_id(EntityKind.TASK)
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir()
    (task_dir / "task.toml").write_text(
        f"""
[identity]
id = "{identity_id}"
key = "{task_id}"
version = 1

[metadata]
difficulty = "easy"
lifecycle = "proposed"
visibility = "public"
tags = ["snapshot"]

[agent]
timeout_sec = 60
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text(
        "Solve the task and write /workspace/output.md.\n",
        encoding="utf-8",
    )
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    (task_dir / "environment" / "data.json").write_text('{"value": 1}\n', encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").chmod(0o755)
    return task_dir
