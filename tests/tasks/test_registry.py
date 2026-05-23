# ABOUTME: Tests for the in-memory task registry in the aec-bench Python implementation.
# ABOUTME: Covers loading, lookup, filtered queries, reload failure tolerance, and error reporting.

from pathlib import Path

from aec_bench.contracts.task_definition import Lifecycle
from aec_bench.tasks.registry import TaskRegistry

TASKS_ROOT = Path(__file__).resolve().parents[2] / "tasks"


def test_registry_loads_and_looks_up_real_tasks() -> None:
    registry = TaskRegistry(tasks_root=TASKS_ROOT)
    registry.reload()

    task = registry.get("mechanical/heat-load/single-room-office/brisbane-office-85m2")

    assert task is not None
    assert task.task_type == "heat-load"


def test_registry_loads_top_level_electrical_task() -> None:
    registry = TaskRegistry(tasks_root=TASKS_ROOT)
    registry.reload()

    task = registry.get("electrical/voltage-drop")

    assert task is not None
    assert task.verifier.expected_output_path == "/workspace/output.md"


def test_registry_filters_loaded_tasks() -> None:
    registry = TaskRegistry(tasks_root=TASKS_ROOT)
    registry.reload()

    selected = registry.filter(domains=["mechanical"])

    assert selected
    assert all(task.domain == "mechanical" for task in selected)


def test_registry_filter_applies_explicit_lifecycle() -> None:
    registry = TaskRegistry(tasks_root=TASKS_ROOT)
    registry.reload()

    all_tasks = registry.all()
    active_only = registry.filter(lifecycle=[Lifecycle.ACTIVE])

    assert len(all_tasks) > 0
    assert len(active_only) == 0  # all loaded tasks are PROPOSED by default


def test_registry_survives_malformed_task(tmp_path: Path) -> None:
    good_dir = tmp_path / "mechanical" / "heat-load" / "good"
    (good_dir / "environment").mkdir(parents=True)
    (good_dir / "tests").mkdir(parents=True)
    (good_dir / "instruction.md").write_text("Write findings to /workspace/output.jsonl.\n", encoding="utf-8")
    (good_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (good_dir / "task.toml").write_text("[agent]\ntimeout_sec = 600\n\n[metadata]\n", encoding="utf-8")

    bad_dir = tmp_path / "mechanical" / "heat-load" / "bad"
    (bad_dir / "tests").mkdir(parents=True)
    (bad_dir / "instruction.md").write_text("Broken task.\n", encoding="utf-8")
    (bad_dir / "task.toml").write_text("[agent]\ntimeout_sec = 600\n\n[metadata]\n", encoding="utf-8")
    # no verifier script — will cause LoadError

    registry = TaskRegistry(tasks_root=tmp_path)
    registry.reload()

    assert len(registry.all()) == 1
    assert registry.all()[0].task_id == "mechanical/heat-load/good"
    assert len(registry.load_errors) == 1
    assert "bad" in str(registry.load_errors[0][0])


def test_registry_returns_empty_for_nonexistent_root(tmp_path: Path) -> None:
    registry = TaskRegistry(tasks_root=tmp_path / "does-not-exist")
    registry.reload()

    assert registry.all() == []
    assert registry.load_errors == []
