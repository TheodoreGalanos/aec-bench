# ABOUTME: Tests for the aec-bench swarm CLI commands.
# ABOUTME: Verifies command registration, config validation, and help output.

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()

# Minimal valid config matching SwarmConfig required fields
_MINIMAL_CONFIG = {
    "task": {
        "workspace": "./workspaces/test",
        "task_path": "tasks/electrical/voltage-drop",
    },
    "agents": {
        "default_model": "anthropic.claude-sonnet-4-20250514",
    },
    "budget": {
        "max_cost_usd": 50.0,
        "eval_budget_usd": 10.0,
    },
}


def test_swarm_help() -> None:
    result = runner.invoke(app, ["swarm", "--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "status" in result.output
    assert "history" in result.output


def test_swarm_run_missing_config() -> None:
    result = runner.invoke(app, ["swarm", "run", "nonexistent.yaml"])
    assert result.exit_code != 0


def test_swarm_run_validates_config(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(yaml.dump({"agents": {"count": 4}}))
    result = runner.invoke(app, ["swarm", "run", str(config_path)])
    assert result.exit_code != 0


def test_swarm_run_missing_workspace(tmp_path: Path) -> None:
    """Valid config but workspace directory doesn't exist → exit 1."""
    config_path = tmp_path / "swarm.yaml"
    config_path.write_text(yaml.dump(_MINIMAL_CONFIG))
    result = runner.invoke(app, ["swarm", "run", str(config_path)])
    assert result.exit_code != 0


def test_swarm_status_missing_run() -> None:
    result = runner.invoke(app, ["swarm", "status", "nonexistent-run-id"])
    assert result.exit_code != 0


def test_swarm_history_no_runs(tmp_path: Path) -> None:
    result = runner.invoke(app, ["swarm", "history", "--state-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "No swarm runs found" in result.output


def test_swarm_resume_missing_log(tmp_path: Path) -> None:
    result = runner.invoke(app, ["swarm", "resume", "sw-missing", "--state-dir", str(tmp_path)])
    assert result.exit_code != 0


def test_swarm_stop_outputs_run_id() -> None:
    result = runner.invoke(app, ["swarm", "stop", "sw-test-123"])
    assert result.exit_code == 0
    assert "sw-test-123" in result.output
