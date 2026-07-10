# ABOUTME: CLI tests for composite task-world template examples.
# ABOUTME: Verifies list, materialize-example, and verify-example commands use JSON envelopes.

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()


def test_task_composite_template_list_command_emits_template_catalogue() -> None:
    result = runner.invoke(app, ["--json", "task", "composite-template", "list"])

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "task composite-template list"
    assert envelope["data"]["count"] == 25
    assert envelope["data"]["templates"][0]["template_id"] == "stormwater-drainage-package"
    assert envelope["data"]["templates"][-1]["template_id"] == "level-crossing-warning-issue-review-package"


def test_task_composite_template_materialize_and_verify_commands(tmp_path: Path) -> None:
    output_dir = tmp_path / "example"

    materialized = runner.invoke(
        app,
        [
            "--json",
            "task",
            "composite-template",
            "materialize-example",
            "pump-station-duty-package",
            "--output",
            str(output_dir),
        ],
    )
    verified = runner.invoke(
        app,
        [
            "--json",
            "task",
            "composite-template",
            "verify-example",
            str(output_dir),
        ],
    )

    assert materialized.exit_code == 0, materialized.output
    assert verified.exit_code == 0, verified.output
    materialized_envelope = json.loads(materialized.output)
    verified_envelope = json.loads(verified.output)
    assert materialized_envelope["data"]["package_dir"] == str(output_dir)
    assert materialized_envelope["data"]["template_id"] == "pump-station-duty-package"
    assert verified_envelope["data"]["overall"] == "pass"
    assert verified_envelope["data"]["template_id"] == "pump-station-duty-package"
