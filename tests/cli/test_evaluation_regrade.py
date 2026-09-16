# ABOUTME: Tests recorded-trial regrading through the public evaluation CLI.
# ABOUTME: Checks side-effect-free planning, verifier failures, and optional execution support.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from harbor.models.trial.config import TrialConfig  # type: ignore[import-untyped]
from typer.testing import CliRunner

from aec_bench.cli import optional_dependencies
from aec_bench.cli.main import app
from aec_bench.harness import harbor_regrade
from tests.support.harbor_regrade import local_verifier_environment, recorded_trial


def _command(source: Path, task: Path, output: Path) -> list[str]:
    return ["--json", "evaluation", "regrade", str(source), "--task", str(task), "--output", str(output)]


def test_regrade_dry_run_checks_inputs_without_writes(tmp_path: Path) -> None:
    source, task = recorded_trial(tmp_path)
    output = tmp_path / "assessment"
    result = CliRunner().invoke(app, [*_command(source, task, output), "--dry-run"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    assert data["dry_run"] is True
    assert data["agent_rerun"] is False
    assert data["backend"] == "docker"
    assert "Harbor checks artifact coverage" in data["validation"]
    assert not output.exists()


@pytest.mark.parametrize("verifier_fails", [False, True])
def test_regrade_cli_reports_distinct_assessment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verifier_fails: bool
) -> None:
    source, task = recorded_trial(tmp_path)
    if verifier_fails:
        (task / "tests" / "test.sh").write_text("#!/usr/bin/env bash\nexit 17\n")
    original_plan = harbor_regrade.plan_regrade

    def local_plan(**kwargs: Any) -> TrialConfig:
        kwargs["environment"] = local_verifier_environment()
        return original_plan(**kwargs)

    monkeypatch.setattr(harbor_regrade, "plan_regrade", local_plan)
    output = tmp_path / "assessment"
    result = CliRunner().invoke(app, _command(source, task, output))
    assert result.exit_code == (2 if verifier_fails else 0), result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == ("partial" if verifier_fails else "success")
    data = envelope["data"]
    assert data["status"] == ("failed" if verifier_fails else "completed")
    assert data["original_rewards"] == {"reward": 0.0}
    assert data["rewards"] == (None if verifier_fails else {"reward": 1.0})
    assert data["agent_rerun"] is False
    assert "cost" not in data
    assert Path(data["result"]).is_file()
    assert bool(data["error"]) is verifier_fails


def test_regrade_reports_missing_execution_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(optional_dependencies, "find_spec", lambda _: None)
    result = CliRunner().invoke(app, _command(Path("source"), Path("task"), Path("assessment")))
    assert result.exit_code == 1
    assert 'pip install "aec-bench[execution]"' in result.output


def test_regrade_cli_rejects_shared_verifier(tmp_path: Path) -> None:
    source, task = recorded_trial(tmp_path)
    config = task / "task.toml"
    config.write_text(config.read_text().replace("separate", "shared"))
    result = CliRunner().invoke(app, [*_command(source, task, tmp_path / "assessment"), "--dry-run"])
    assert result.exit_code != 0
    assert "shared-mode verifier" in result.output
