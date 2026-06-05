# ABOUTME: Tests for the manifest and inline aec-bench run CLI entry point.
# ABOUTME: Verifies backend planning output and Harbor-backed Morph routing.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app

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
