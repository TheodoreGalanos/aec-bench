# ABOUTME: Tests the installed current lifecycle command group.
# ABOUTME: Confirms obsolete composite-template routes are absent.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()


def _payload(result_output: str) -> dict[str, object]:
    payload = json.loads(result_output)
    if not isinstance(payload, dict):
        raise AssertionError("expected CLI JSON object")
    return payload


def _error_messages(result_output: str, command: str) -> list[str]:
    envelope = _payload(result_output)
    assert envelope["command"] == command
    assert envelope["status"] == "error"
    assert envelope["data"] is None
    errors = envelope["errors"]
    assert isinstance(errors, list)
    assert errors
    assert all(isinstance(error, str) for error in errors)
    return errors


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


@pytest.mark.parametrize(
    ("subcommand", "argument_template"),
    [
        ("start", ("--package", "{package}", "--run-dir", "{run_dir}")),
        ("submit", ("--package", "{package}", "--run-dir", "{run_dir}")),
        ("status", ("--package", "{package}", "--run-dir", "{run_dir}")),
        (
            "revisit",
            (
                "--package",
                "{package}",
                "--run-dir",
                "{run_dir}",
                "--checkpoint-id",
                "checkpoint-1",
                "--reason",
                "Inspect the prior evidence.",
            ),
        ),
        (
            "branch",
            (
                "--package",
                "{package}",
                "--parent-run-dir",
                "{run_dir}",
                "--branch-run-dir",
                "{branch_run_dir}",
                "--checkpoint-id",
                "checkpoint-1",
                "--branch-id",
                "branch-1",
                "--reason",
                "Test an alternative.",
            ),
        ),
        (
            "run",
            ("--package", "{package}", "--run-dir", "{run_dir}", "--model", "test-model"),
        ),
        ("verify", ("{package}", "--run-dir", "{run_dir}")),
    ],
)
def test_task_lifecycle_expected_io_errors_use_json_envelope(
    tmp_path: Path,
    subcommand: str,
    argument_template: tuple[str, ...],
) -> None:
    package = tmp_path / "missing-package"
    values = {
        "package": str(package),
        "run_dir": str(tmp_path / "run"),
        "branch_run_dir": str(tmp_path / "branch-run"),
    }
    arguments = [argument.format_map(values) for argument in argument_template]

    result = runner.invoke(app, ["--json", "task", "lifecycle", subcommand, *arguments])

    assert result.exit_code == 1
    errors = _error_messages(result.output, f"task lifecycle {subcommand}")
    assert str(package / "template.json") in errors[0]


def test_task_lifecycle_json_error_uses_json_envelope(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "template.json").write_text("{", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--json",
            "task",
            "lifecycle",
            "run",
            "--package",
            str(package),
            "--run-dir",
            str(tmp_path / "run"),
            "--model",
            "test-model",
        ],
    )

    assert result.exit_code == 1
    errors = _error_messages(result.output, "task lifecycle run")
    assert "Expecting property name enclosed in double quotes" in errors[0]


def test_task_lifecycle_domain_error_uses_json_envelope(tmp_path: Path) -> None:
    package = tmp_path / "package"
    run_dir = tmp_path / "run"
    materialized = runner.invoke(
        app,
        [
            "--json",
            "task",
            "lifecycle",
            "materialize",
            "drainage-model-evidence-lifecycle-review",
            "--output",
            str(package),
        ],
    )
    started = runner.invoke(
        app,
        [
            "--json",
            "task",
            "lifecycle",
            "start",
            "--package",
            str(package),
            "--run-dir",
            str(run_dir),
        ],
    )

    assert materialized.exit_code == 0, materialized.output
    assert started.exit_code == 0, started.output

    result = runner.invoke(
        app,
        [
            "--json",
            "task",
            "lifecycle",
            "revisit",
            "--package",
            str(package),
            "--run-dir",
            str(run_dir),
            "--checkpoint-id",
            "initial_review",
            "--reason",
            "Inspect the active checkpoint.",
        ],
    )

    assert result.exit_code == 1
    errors = _error_messages(result.output, "task lifecycle revisit")
    assert errors == ["checkpoint is not available for revisit: initial_review"]
