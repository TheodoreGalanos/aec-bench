# ABOUTME: Tests the installed world conformance command for every maintained world.
# ABOUTME: Protects canonical-key lookup, positive results, and clear unknown-key errors.

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.worlds.conformance import (
    REQUIRED_GUARANTEES,
    WorldConformanceCase,
    WorldConformanceScenario,
    run_world_conformance,
)
from aec_bench.worlds.runtime.world_logic import ActionRejected

runner = CliRunner()


def test_world_conformance_command_runs_every_maintained_world() -> None:
    for world_key in ("monitoring/dam-seepage", "stewardship/wastewater-pump-station"):
        result = runner.invoke(app, ["--json", "conformance", "world", world_key])

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["data"]["world_key"] == world_key
        assert payload["data"]["proven"]
        assert REQUIRED_GUARANTEES <= set(payload["data"]["proven"])
        assert "state_serialization" in payload["data"]["proven"]
        assert "observation_serialization" in payload["data"]["proven"]


def test_world_conformance_command_rejects_unknown_key() -> None:
    result = runner.invoke(app, ["--json", "conformance", "world", "unknown/world"])

    assert result.exit_code == 1
    assert "unknown world key" in result.stderr


def test_runner_rejects_a_case_without_owner_proof() -> None:
    case = WorldConformanceCase(
        world_key="test/world",
        scenario=lambda _seed: WorldConformanceScenario(
            initial_state=lambda _seed: object(),
            observe=lambda state: state,
            transition=lambda _state, _action: ActionRejected("test", "test rejection"),
            actions=(),
            invalid_action=object(),
            assert_observation_safe=lambda _observation: None,
        ),
        requires_terminal_rejection=True,
    )

    with pytest.raises(AssertionError, match="missing required proofs"):
        run_world_conformance(case)
