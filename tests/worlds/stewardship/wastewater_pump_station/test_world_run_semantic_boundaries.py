# ABOUTME: Tests current opaque-decision semantic boundaries for the registered pump world.
# ABOUTME: Proves stale or forged decisions cannot mutate the selected history.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.contracts.world_interface import WorldActorActionRequest, WorldInterfaceError
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _start(root: Path) -> PumpStationWorldRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="boundary-run",
        episode_id="boundary-episode",
        world_branch_id="boundary-branch",
    )


def test_forged_decision_cannot_mutate_current_history(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    before = run.snapshot()

    with pytest.raises(WorldInterfaceError, match="decision-stale"):
        PumpStationEpisodeHost(root).invoke(
            WorldActorActionRequest(
                request_id="forged-action",
                decision_id="forged-decision",
                action_name="continue_operation",
                arguments={"reason": "This decision was never issued."},
            )
        )

    assert run.snapshot() == before
    assert run.repository.command_steps() == ()


def test_previous_decision_cannot_authorise_a_second_action(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    host = PumpStationEpisodeHost(root)
    decision_id = host.observe().decision_id
    host.invoke(
        WorldActorActionRequest(
            request_id="accepted-action",
            decision_id=decision_id,
            action_name="continue_operation",
            arguments={"reason": "Consume the current decision."},
        )
    )

    with pytest.raises(WorldInterfaceError, match="decision-stale"):
        PumpStationEpisodeHost(root).invoke(
            WorldActorActionRequest(
                request_id="stale-action",
                decision_id=decision_id,
                action_name="continue_operation",
                arguments={"reason": "Reuse an expired decision."},
            )
        )

    assert run.snapshot().sequence == 1
    assert len(run.repository.command_steps()) == 1
