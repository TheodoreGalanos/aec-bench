# ABOUTME: CLI integration tests for creating versioned benchmark datasets.
# ABOUTME: Covers task selection filters exposed by the dataset create command.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()


def _make_task(project_root: Path, task_id: str, difficulty: str) -> None:
    task_dir = project_root / "tasks" / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        "[metadata]\n"
        f'difficulty = "{difficulty}"\n'
        'category = "reasoning"\n'
        'tags = ["dataset-test"]\n\n'
        "[agent]\n"
        "timeout_sec = 600\n",
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text(
        "Solve the task and write the answer to `/workspace/output.md`.\n",
        encoding="utf-8",
    )
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")


def _prepare_project(tmp_path: Path) -> None:
    (tmp_path / "aec-bench.toml").write_text(
        '[paths]\ntasks = "tasks"\ndatasets = "artefacts/datasets"\n',
        encoding="utf-8",
    )
    _make_task(tmp_path, "electrical/example/easy", "easy")
    _make_task(tmp_path, "electrical/example/medium", "medium")
    _make_task(tmp_path, "mechanical/example/hard", "hard")


def _write_suite_output(project_root: Path) -> Path:
    suite_output = project_root / "tasks" / "dataset.json"
    suite_output.write_text(
        json.dumps(
            {
                "name": "generated-suite",
                "seed": 20260508,
                "created": "2026-05-08T00:00:00Z",
                "framework_version": "0.1.0",
                "config": "suite.toml",
                "summary": {
                    "total_instances": 2,
                    "by_discipline": {"electrical": 1, "mechanical": 1},
                    "by_difficulty": {"easy": 1, "hard": 1},
                    "by_visibility": {"all_given": 2},
                    "by_tool_mode": {"with-tool": 2},
                },
                "instances": [
                    {
                        "path": "electrical/example/easy",
                        "template": "example",
                        "difficulty": "easy",
                        "archetype": "test",
                        "site_context": "test",
                        "visibility": "all_given",
                        "tool_mode": "with-tool",
                    },
                    {
                        "path": "mechanical/example/hard",
                        "template": "example",
                        "difficulty": "hard",
                        "archetype": "test",
                        "site_context": "test",
                        "visibility": "all_given",
                        "tool_mode": "with-tool",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return suite_output


def test_dataset_create_filters_by_difficulty(tmp_path: Path, monkeypatch) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "--json",
            "dataset",
            "create",
            "--name",
            "easy-only",
            "--version",
            "1.0.0",
            "--difficulty",
            "easy",
        ],
    )

    assert result.exit_code == 0, result.output
    manifest_path = tmp_path / "artefacts" / "datasets" / "easy-only" / "1.0.0" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [task["task_id"] for task in manifest["tasks"]] == ["electrical/example/easy"]
    assert manifest["description"]["difficulty_distribution"] == {"easy": 1}


def test_dataset_create_rejects_unknown_difficulty(tmp_path: Path, monkeypatch) -> None:
    _prepare_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "dataset",
            "create",
            "--name",
            "bad-difficulty",
            "--version",
            "1.0.0",
            "--difficulty",
            "heroic",
        ],
    )

    assert result.exit_code == 1
    assert "unknown difficulty: heroic" in result.output


def test_dataset_create_from_suite_output_freezes_exact_instances(tmp_path: Path, monkeypatch) -> None:
    _prepare_project(tmp_path)
    suite_output = _write_suite_output(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "dataset",
            "create",
            "--name",
            "from-suite",
            "--version",
            "1.0.0",
            "--from-suite-output",
            str(suite_output),
        ],
    )

    assert result.exit_code == 0, result.output
    manifest_path = tmp_path / "artefacts" / "datasets" / "from-suite" / "1.0.0" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [task["task_id"] for task in manifest["tasks"]] == [
        "electrical/example/easy",
        "mechanical/example/hard",
    ]
    assert manifest["source"]["method"] == "suite_config"
    assert manifest["source"]["seed"] == 20260508
    assert manifest["source"]["suite_config"]["suite_output"] == str(suite_output.resolve())


def test_dataset_create_from_suite_output_rejects_selection_filters(tmp_path: Path, monkeypatch) -> None:
    _prepare_project(tmp_path)
    suite_output = _write_suite_output(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "dataset",
            "create",
            "--name",
            "ambiguous",
            "--version",
            "1.0.0",
            "--from-suite-output",
            str(suite_output),
            "--difficulty",
            "easy",
        ],
    )

    assert result.exit_code == 1
    assert "--from-suite-output cannot be combined" in result.output
