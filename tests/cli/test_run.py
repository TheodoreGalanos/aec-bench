# ABOUTME: Tests for the manifest and inline aec-bench run CLI entry point.
# ABOUTME: Verifies backend planning output and Harbor-backed Morph routing.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.contracts.dataset import DatasetManifest, DatasetTaskEntry
from aec_bench.dataset.publication import publish_dataset

runner = CliRunner()


def _write_minimal_task(tasks_root: Path) -> Path:
    task_dir = tasks_root / "electrical" / "voltage-drop" / "demo-instance"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "instruction.md").write_text(
        "Calculate the answer and write it to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        '[metadata]\nvisibility = "public"\n\n[agent]\ntimeout_sec = 60\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return task_dir


def test_run_dry_run_reports_selected_backend(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_minimal_task(tasks_root)

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            str(task_dir),
            "--model",
            "test-model",
            "--tasks-root",
            str(tasks_root),
            "--backend",
            "modal",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["backend"] == "modal"


def test_run_dry_run_accepts_morph_backend(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_minimal_task(tasks_root)

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            str(task_dir),
            "--model",
            "test-model",
            "--tasks-root",
            str(tasks_root),
            "--backend",
            "morph",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["backend"] == "morph"


def test_run_dry_run_reports_reviewer_plan_from_config(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_minimal_task(tasks_root)
    reviewer_config = tmp_path / "reviewer.json"
    reviewer_config.write_text(
        json.dumps(
            {
                "enabled": True,
                "models": [
                    {"name": "primary", "model": "openai:gpt-5.2"},
                    {"name": "secondary", "model": "anthropic:claude-opus-4-8"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            str(task_dir),
            "--model",
            "test-model",
            "--tasks-root",
            str(tasks_root),
            "--backend",
            "modal",
            "--reviewer-models-config",
            str(reviewer_config),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["reviewer"]["enabled"] is True
    assert envelope["data"]["reviewer"]["models"] == ["primary", "secondary"]


def test_run_config_resolves_dataset_label_before_planning(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_minimal_task(tasks_root)
    task_path = task_dir.relative_to(tmp_path).as_posix()
    manifest = DatasetManifest(
        dataset_id="core",
        description="Core benchmark tasks",
        tasks=(
            DatasetTaskEntry(task_id=task_dir.relative_to(tasks_root).as_posix(), path=task_path, task_kind="artifact"),
        ),
    )
    publish_dataset(
        manifest=manifest,
        datasets_root=tmp_path / "artefacts" / "datasets",
        project_root=tmp_path,
        label="public-2026",
    )
    config = tmp_path / "experiment.yaml"
    config.write_text(
        """\
experiment_id: exact-dataset
name: Exact dataset run
tasks:
  dataset: core@public-2026
agents:
  - name: test-agent
    adapter: tool_loop
    model: test-model
compute:
  backend: modal
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--json",
            "run",
            "--config",
            str(config),
            "--tasks-root",
            str(tasks_root),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["selected_tasks"] == 1
