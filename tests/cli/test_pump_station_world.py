# ABOUTME: Tests public CLI wiring for registered pump-station world execution.
# ABOUTME: Proves trial-wide actor limits reach the Harbor job and emitted evidence.

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from aec_bench.cli.main import app


def test_run_harbor_forwards_and_reports_world_action_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            config_path=tmp_path / "job.yaml",
            command=("harbor", "run"),
            exit_code=None,
        )

    monkeypatch.setattr(
        "aec_bench.cli.commands.pump_station_world.require_optional_extra",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "aec_bench.cli.harbor_environment.resolve_harbor_environment_binding",
        lambda _backend: None,
    )
    monkeypatch.setattr(
        "aec_bench.harness.pump_station_harbor.job.run_pump_station_harbor_job",
        fake_run,
    )

    result = CliRunner().invoke(
        app,
        [
            "--json",
            "task",
            "pump-station-world",
            "run-harbor",
            "--task-dir",
            str(tmp_path / "task"),
            "--project-root",
            str(tmp_path),
            "--jobs-dir",
            str(tmp_path / "jobs"),
            "--config-path",
            str(tmp_path / "job.yaml"),
            "--model",
            "azure:model",
            "--adapter",
            "deepseek_harness",
            "--max-world-actions",
            "7",
            "--no-execute",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["max_world_actions"] == 7
    payload = json.loads(result.output)
    assert payload["data"]["limits"]["max_world_actions"] == 7
