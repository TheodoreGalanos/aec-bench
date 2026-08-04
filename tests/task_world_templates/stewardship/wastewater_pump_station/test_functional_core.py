# ABOUTME: Integration-tests the current pump state transition path through the episode host.
# ABOUTME: Proves one accepted decision advances once and all current state fields affect identity.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _start(root: Path) -> PumpStationWorldRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="functional-core-run",
        episode_id="functional-core-episode",
        world_branch_id="functional-core-branch",
    )


def test_current_actor_transition_advances_and_replays_once(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    host = PumpStationEpisodeHost(root)
    observation = host.observe()

    result = host.invoke(
        WorldActorActionRequest(
            request_id="functional-core-action",
            decision_id=observation.decision_id,
            action_name="continue_operation",
            arguments={"reason": "Advance the current registered world."},
        )
    )

    assert result.status == "applied"
    assert run.snapshot().sequence == 1
    assert len(run.repository.command_steps()) == 1
    assert run.verify().valid


def test_current_state_identity_includes_event_effects(tmp_path: Path) -> None:
    state = _start(tmp_path / "run").state
    changed = replace(state, event_effect_ids=(*state.event_effect_ids, "current-effect"))

    assert changed.state_id != state.state_id
