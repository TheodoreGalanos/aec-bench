# ABOUTME: Tests the installed current lifecycle command group.
# ABOUTME: Confirms obsolete composite-template routes are absent.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()


def _payload(result_output: str) -> dict[str, object]:
    payload = json.loads(result_output)
    if not isinstance(payload, dict):
        raise AssertionError("expected CLI JSON object")
    return payload


def test_task_lifecycle_lists_only_current_task_definitions() -> None:
    result = runner.invoke(app, ["--json", "task", "lifecycle", "list"])

    assert result.exit_code == 0
    envelope = _payload(result.output)
    assert envelope["command"] == "task lifecycle list"
    data = envelope["data"]
    assert isinstance(data, dict)
    assert data["count"] == 4
    assert {item["template_id"] for item in data["lifecycles"]} == {
        "drainage-model-evidence-lifecycle-review",
        "facade-submittal-review-lifecycle",
        "hydraulic-design-response-lifecycle-review",
        "hydraulic-interaction-lifecycle-review",
    }


def test_task_lifecycle_materializes_current_metadata(tmp_path: Path) -> None:
    output = tmp_path / "package"
    result = runner.invoke(
        app,
        [
            "--json",
            "task",
            "lifecycle",
            "materialize",
            "drainage-model-evidence-lifecycle-review",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    metadata = json.loads((output / "template.json").read_text(encoding="utf-8"))
    assert set(metadata) == {"template_id", "name", "discipline"}
    assert (output / "lifecycle.json").is_file()
    assert not (output / "world.json").exists()


def test_task_lifecycle_lists_variants_and_rejects_unknown_variant(tmp_path: Path) -> None:
    listed = runner.invoke(
        app,
        ["--json", "task", "lifecycle", "list-variants", "hydraulic-interaction-lifecycle-review"],
    )
    rejected = runner.invoke(
        app,
        [
            "--json",
            "task",
            "lifecycle",
            "materialize",
            "hydraulic-interaction-lifecycle-review",
            "--variant",
            "missing",
            "--output",
            str(tmp_path / "package"),
        ],
    )

    assert listed.exit_code == 0
    data = _payload(listed.output)["data"]
    assert isinstance(data, dict)
    assert data["variants"] == [
        "administrative_no_op",
        "major_idf_revision",
        "outlet_geometry_revision",
        "tailwater_revision",
    ]
    assert rejected.exit_code == 1
    assert "unknown lifecycle variant" in rejected.output


def test_obsolete_composite_template_command_is_not_installed() -> None:
    result = runner.invoke(app, ["task", "composite-template", "list"])

    assert result.exit_code != 0
    assert "No such command 'composite-template'" in result.output


def test_task_lifecycle_contains_complete_command_hierarchy() -> None:
    lifecycle_help = runner.invoke(app, ["task", "lifecycle", "--help"])
    study_help = runner.invoke(app, ["task", "lifecycle", "study", "--help"])

    assert lifecycle_help.exit_code == 0
    assert study_help.exit_code == 0
    for command in (
        "list",
        "list-variants",
        "materialize",
        "start",
        "submit",
        "status",
        "revisit",
        "branch",
        "run",
        "verify",
        "run-smoke",
        "study",
    ):
        assert command in lifecycle_help.output
    assert "ablation" in study_help.output
    assert "calibration-freeze" in study_help.output
