# ABOUTME: Exercises the current registered pump world end to end through opaque decisions.
# ABOUTME: Proves equivalent episodes produce the same state and replay evidence.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _execute(root: Path) -> PumpStationWorldRun:
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="deterministic-run",
        episode_id="deterministic-episode",
        world_branch_id="deterministic-branch",
    )
    host = PumpStationEpisodeHost(root)
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id="deterministic-action",
            decision_id=observation.decision_id,
            action_name="continue_operation",
            arguments={"reason": "Advance the same current episode."},
        )
    )
    return run


def test_current_registered_episode_is_deterministic(tmp_path: Path) -> None:
    first = _execute(tmp_path / "first")
    second = _execute(tmp_path / "second")

    assert first.state == second.state
    assert first.snapshot().state_id == second.snapshot().state_id
    assert first.repository.command_steps() == second.repository.command_steps()
    assert first.verify() == second.verify()
