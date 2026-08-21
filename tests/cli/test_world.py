# ABOUTME: Tests public Interactive World discovery and direct planning through the CLI.
# ABOUTME: Proves commands use the public facade and reject unsupported routes before execution.

import json

from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()


def test_world_discovery_commands_use_public_values() -> None:
    result = runner.invoke(app, ["--json", "task", "world", "list"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["data"]
    assert [item["id"] for item in payload] == [
        "dam-seepage-monitoring",
        "wastewater-pump-station-stewardship.v1",
    ]
    assert payload[1]["capabilities"] == ["branching", "host-controls", "persistence"]


def test_world_run_dry_run_plans_without_provider_execution() -> None:
    result = runner.invoke(
        app,
        [
            "--json",
            "task",
            "world",
            "run",
            "dam-seepage-monitoring",
            "--profile",
            "synthetic-rising-seepage",
            "--instruction",
            "Monitor the dam.",
            "--model",
            "test-model",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["data"]
    assert payload["task"]["task_id"] == "dam-seepage-monitoring/synthetic-rising-seepage"
    assert len(payload["trials"]) == 1


def test_world_run_rejects_unsupported_provider_before_execution() -> None:
    result = runner.invoke(
        app,
        [
            "--json",
            "task",
            "world",
            "run",
            "dam-seepage-monitoring",
            "--profile",
            "synthetic-rising-seepage",
            "--instruction",
            "Monitor the dam.",
            "--model",
            "test-model",
            "--adapter",
            "deepseek_harness",
            "--dry-run",
        ],
    )

    assert result.exit_code == 1
    assert "unsupported world trial route" in result.output


def test_old_pump_command_path_is_absent() -> None:
    result = runner.invoke(app, ["task", "pump-station-world", "--help"])

    assert result.exit_code == 2
    assert "No such command" in result.output
