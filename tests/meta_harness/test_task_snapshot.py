# ABOUTME: Tests deterministic runnable-task snapshots used by adaptive RunBundles.
# ABOUTME: Verifies canonical definitions, package bytes, file modes, ordering, and path containment.

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.run_bundle import WorldSnapshotRef
from aec_bench.meta_harness.task_snapshot import (
    TaskSnapshotError,
    build_task_snapshot,
    graph_hidden_task_snapshot_sha256,
    resolve_task_snapshots,
)
from aec_bench.tasks.loader import load_task_definition


def test_task_snapshot_binds_definition_and_all_runnable_package_bytes(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/example")
    task = load_task_definition(task_dir, tasks_root)

    first = build_task_snapshot(task=task, tasks_root=tasks_root)
    second = build_task_snapshot(task=task, tasks_root=tasks_root)

    assert first == second
    assert first.task_id == task.task_id
    assert len(first.definition_sha256) == 64
    assert len(first.package_sha256) == 64

    (task_dir / "environment" / "data.json").write_text('{"value": 2}\n', encoding="utf-8")
    changed_bytes = build_task_snapshot(
        task=load_task_definition(task_dir, tasks_root),
        tasks_root=tasks_root,
    )
    assert changed_bytes.definition_sha256 == first.definition_sha256
    assert changed_bytes.package_sha256 != first.package_sha256


def test_graph_hidden_snapshot_identity_rejects_a_world_bearing_package(tmp_path: Path) -> None:
    """A proposer-facing snapshot hash can only identify a physically graph-hidden package."""
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/example")
    snapshot = build_task_snapshot(
        task=load_task_definition(task_dir, tasks_root),
        tasks_root=tasks_root,
    )

    assert graph_hidden_task_snapshot_sha256(snapshot) == canonical_content_sha256(
        {
            "task_id": snapshot.task_id,
            "definition_sha256": snapshot.definition_sha256,
            "package_sha256": snapshot.package_sha256,
        }
    )

    world_bearing = snapshot.model_copy(
        update={
            "world": WorldSnapshotRef(
                world_id="world.example",
                world_envelope_sha256="1" * 64,
                world_package_sha256="2" * 64,
                topology_signature_sha256="3" * 64,
                visibility="public",
            )
        }
    )
    with pytest.raises(TaskSnapshotError, match="graph-hidden"):
        graph_hidden_task_snapshot_sha256(world_bearing)


def test_task_snapshot_derives_world_lineage_from_a_strict_profile_sidecar(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/example")
    world_payload: dict[str, Any] = {
        "world_id": "aec.world.civil.calculation",
        "name": "Civil calculation world",
        "task_unit": "generated-task-instance",
        "logic_profile": {"closure_gates": [], "agentic_review": {"required": True}},
        "operation_profile": {
            "subset_axes": ["inputs"],
            "difference_axes": ["method"],
            "projection_axes": ["answer"],
            "product_axes": ["discipline", "method"],
        },
    }
    (task_dir / "world.json").write_text(json.dumps(world_payload, indent=2) + "\n", encoding="utf-8")

    snapshot = build_task_snapshot(
        task=load_task_definition(task_dir, tasks_root),
        tasks_root=tasks_root,
    )

    assert snapshot.world is not None
    assert snapshot.world.world_id == "aec.world.civil.calculation"
    assert len(snapshot.world.world_envelope_sha256) == 64
    assert len(snapshot.world.world_package_sha256) == 64
    assert len(snapshot.world.topology_signature_sha256) == 64
    assert snapshot.world.visibility.value == "public"


def test_task_snapshot_topology_signature_uses_only_declared_reward_blind_graph_fields(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/topology")
    world_payload: dict[str, Any] = {
        "world_id": "aec.world.civil.topology",
        "name": "Topology world",
        "task_unit": "review-family",
        "logic_profile": {"agentic_review": {"required": True}},
        "stages": [{"id": "intake"}, {"id": "review"}, {"id": "decision"}],
        "handoffs": [
            {
                "id": "intake-review",
                "producer_stage": "intake",
                "consumer_stages": ["review"],
                "example_value": "gold-a",
            },
            {
                "id": "review-decision",
                "producer_stage": "review",
                "consumer_stages": ["decision"],
                "example_value": "gold-b",
            },
        ],
    }
    sidecar = task_dir / "world.json"
    sidecar.write_text(json.dumps(world_payload, indent=2) + "\n", encoding="utf-8")
    task = load_task_definition(task_dir, tasks_root)
    serial = build_task_snapshot(task=task, tasks_root=tasks_root)

    world_payload["handoffs"][0]["example_value"] = "changed hidden example"
    sidecar.write_text(json.dumps(world_payload, indent=2) + "\n", encoding="utf-8")
    hidden_changed = build_task_snapshot(task=task, tasks_root=tasks_root)
    world_payload["handoffs"][0]["consumer_stages"] = ["decision"]
    sidecar.write_text(json.dumps(world_payload, indent=2) + "\n", encoding="utf-8")
    graph_changed = build_task_snapshot(task=task, tasks_root=tasks_root)

    assert serial.world is not None
    assert hidden_changed.world is not None
    assert graph_changed.world is not None
    assert serial.world.topology_signature_sha256 == hidden_changed.world.topology_signature_sha256
    assert serial.world.topology_signature_sha256 != graph_changed.world.topology_signature_sha256


def test_task_snapshot_binds_a_content_addressed_declared_stage_graph(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/staged")
    world_payload: dict[str, Any] = {
        "world_id": "aec.world.civil.staged",
        "name": "Staged civil world",
        "task_unit": "generated-task-instance",
        "logic_profile": {"agentic_review": {"required": True}},
        "stages": [
            {
                "id": "inventory",
                "title": "Inventory",
                "discipline": "civil",
                "consumes": ["document_register"],
                "produces": ["source_inventory"],
            },
            {
                "id": "authority",
                "title": "Authority",
                "discipline": "civil",
                "consumes": ["source_inventory"],
                "produces": ["provenance_ledger"],
            },
            {
                "id": "decision",
                "title": "Decision",
                "discipline": "civil",
                "consumes": ["provenance_ledger"],
                "produces": ["readiness_decision"],
            },
        ],
        "handoffs": [
            {
                "id": "packet_id",
                "producer_stage": "inventory",
                "consumer_stages": ["decision"],
            }
        ],
    }
    sidecar = task_dir / "world.json"
    sidecar.write_text(json.dumps(world_payload, indent=2) + "\n", encoding="utf-8")

    snapshot = build_task_snapshot(
        task=load_task_definition(task_dir, tasks_root),
        tasks_root=tasks_root,
    )

    assert snapshot.world is not None
    graph = snapshot.world.stage_graph
    assert graph is not None
    assert graph.task_id == "civil/calculation/staged"
    assert graph.world_package_sha256 == snapshot.world.world_package_sha256
    assert graph.topological_order == ("inventory", "authority", "decision")
    assert graph.predecessor_stage_ids("decision") == ("inventory", "authority")
    assert graph.required_output_ids("inventory") == ("packet_id", "source_inventory")


def test_task_snapshot_binds_executable_file_mode(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/example")
    task = load_task_definition(task_dir, tasks_root)
    script = task_dir / "tests" / "test.sh"

    script.chmod(0o644)
    non_executable = build_task_snapshot(task=task, tasks_root=tasks_root)
    script.chmod(0o755)
    executable = build_task_snapshot(task=task, tasks_root=tasks_root)

    assert non_executable.package_sha256 != executable.package_sha256


def test_task_snapshot_ignores_only_transient_python_cache_files(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/example")
    task = load_task_definition(task_dir, tasks_root)
    before = build_task_snapshot(task=task, tasks_root=tasks_root)

    cache = task_dir / "environment" / "__pycache__"
    cache.mkdir()
    (cache / "tool.cpython-313.pyc").write_bytes(b"transient")
    (task_dir / ".DS_Store").write_bytes(b"transient")

    assert build_task_snapshot(task=task, tasks_root=tasks_root) == before


def test_task_snapshot_rejects_definition_drift_and_symlinks(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "civil/calculation/example")
    task = load_task_definition(task_dir, tasks_root)
    (task_dir / "instruction.md").write_text("Changed after the task was loaded.\n", encoding="utf-8")

    with pytest.raises(TaskSnapshotError, match="definition changed"):
        build_task_snapshot(task=task, tasks_root=tasks_root)

    current = load_task_definition(task_dir, tasks_root)
    target = tmp_path / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    os.symlink(target, task_dir / "environment" / "outside-link")
    with pytest.raises(TaskSnapshotError, match="symbolic links"):
        build_task_snapshot(task=current, tasks_root=tasks_root)


def test_resolve_task_snapshots_preserves_exact_requested_order(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "civil/calculation/alpha")
    _write_task(tasks_root, "civil/calculation/beta")

    snapshots = resolve_task_snapshots(
        task_refs=("civil/calculation/beta", "civil/calculation/alpha"),
        tasks_root=tasks_root,
    )

    assert tuple(snapshot.task_id for snapshot in snapshots) == (
        "civil/calculation/beta",
        "civil/calculation/alpha",
    )

    with pytest.raises(TaskSnapshotError, match="unknown task refs"):
        resolve_task_snapshots(
            task_refs=("civil/calculation/missing",),
            tasks_root=tasks_root,
        )


def _write_task(tasks_root: Path, task_id: str) -> Path:
    task_dir = tasks_root / task_id
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir()
    (task_dir / "task.toml").write_text(
        """
[metadata]
difficulty = "easy"
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
