# ABOUTME: Tests for `aec-bench library export` CLI driver.
# ABOUTME: Uses Typer's CliRunner against real tmp_path template/seed trees.

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.commands.library import app

runner = CliRunner()


# --- Shared fixture helpers (duplicate of projection tests to keep CLI tests self-contained) ---

TEMPLATE_PARAMS_TOML = """\
[meta]
name = "{name}"
description = "d"
discipline = "{discipline}"
category = "cat1"
standards = ["S1"]
tags = ["t1"]
tool_mode = "with-tool"

[params.x]
type = "float"
description = "x"
unit = "m"
min = 1
max = 10

[outputs.y]
description = "y"
tolerance = 0.03

[difficulty.easy]
description = "e"
visibility = "all_given"
archetypes = []
"""

TEMPLATE_ENGINE_PY = "def compute(**kwargs):\n    return {'y': 1.0}\n"


def _stage(root: Path, name: str, discipline: str = "electrical") -> None:
    tdir = root / discipline / name.replace("-", "_")
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "params.toml").write_text(TEMPLATE_PARAMS_TOML.format(name=name, discipline=discipline), encoding="utf-8")
    (tdir / "engine.py").write_text(TEMPLATE_ENGINE_PY, encoding="utf-8")
    (tdir / "instruction.md").write_text("i", encoding="utf-8")


def test_library_export_writes_to_custom_out(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    _stage(templates_root, "voltage-drop")
    out = tmp_path / "catalogue.json"

    result = runner.invoke(
        app,
        [
            "export",
            "--templates-root",
            str(templates_root),
            "--tasks-root",
            str(tasks_root),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["schema_version"] == 1
    assert len(data["templates"]) == 1


def test_library_export_stdout_mode(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    _stage(templates_root, "voltage-drop")

    result = runner.invoke(
        app,
        [
            "export",
            "--templates-root",
            str(templates_root),
            "--tasks-root",
            str(tasks_root),
            "--stdout",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["schema_version"] == 1


def test_library_export_pretty_indents_output(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    _stage(templates_root, "voltage-drop")
    out = tmp_path / "c.json"

    result = runner.invoke(
        app,
        [
            "export",
            "--templates-root",
            str(templates_root),
            "--tasks-root",
            str(tasks_root),
            "--out",
            str(out),
            "--pretty",
        ],
    )
    assert result.exit_code == 0
    content = out.read_text()
    # Pretty mode uses indented JSON → at least two lines.
    assert content.count("\n") > 2


def test_library_export_out_and_stdout_mutex(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    _stage(templates_root, "x")

    result = runner.invoke(
        app,
        [
            "export",
            "--templates-root",
            str(templates_root),
            "--tasks-root",
            str(tasks_root),
            "--out",
            str(tmp_path / "c.json"),
            "--stdout",
        ],
    )
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output.lower() or "cannot" in result.output.lower()


def test_library_export_empty_library_fails(tmp_path: Path) -> None:
    (tmp_path / "templates").mkdir()
    (tmp_path / "tasks").mkdir()

    result = runner.invoke(
        app,
        [
            "export",
            "--templates-root",
            str(tmp_path / "templates"),
            "--tasks-root",
            str(tmp_path / "tasks"),
            "--out",
            str(tmp_path / "c.json"),
        ],
    )
    assert result.exit_code == 1
    assert "empty" in result.output.lower()


def test_library_export_json_envelope_mode(tmp_path: Path) -> None:
    """--json emits the CLIResult envelope on stdout, still writes the file."""
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    _stage(templates_root, "voltage-drop")
    out = tmp_path / "c.json"

    result = runner.invoke(
        app,
        [
            "export",
            "--templates-root",
            str(templates_root),
            "--tasks-root",
            str(tasks_root),
            "--out",
            str(out),
            "--json",
        ],
    )
    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["command"] == "library export"
    assert envelope["status"] == "success"
    assert envelope["data"]["out_path"].endswith("c.json")
    assert envelope["data"]["total_templates"] == 1
    assert out.exists()
