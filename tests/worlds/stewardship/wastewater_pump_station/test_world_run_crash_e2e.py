# ABOUTME: Proves current registered actor publication recovers exactly once after interruption.
# ABOUTME: Exercises recovery through a newly constructed episode host.

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_current_action_recovers_once_after_interrupted_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="crash-run",
        episode_id="crash-episode",
        world_branch_id="crash-branch",
    )
    interrupted = PumpStationEpisodeHost(root)
    observation = interrupted.observe()
    request = WorldActorActionRequest(
        request_id="crash-action",
        decision_id=observation.decision_id,
        action_name="continue_operation",
        arguments={"reason": "Recover this accepted action once."},
    )

    def fail_selection(_pointer: object) -> None:
        raise OSError("interrupt after immutable staging")

    monkeypatch.setattr(interrupted._repository, "_replace_current", fail_selection)
    with pytest.raises(OSError, match="interrupt after immutable staging"):
        interrupted.invoke(request)

    recovered = PumpStationEpisodeHost(root).invoke(request)

    assert recovered.status == "applied"
    assert run.snapshot().sequence == 1
    assert len(run.repository.command_steps()) == 1
    assert run.verify().valid
