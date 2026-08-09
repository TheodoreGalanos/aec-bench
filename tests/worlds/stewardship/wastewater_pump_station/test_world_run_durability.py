# ABOUTME: Proves read-only resume does not rewrite current pump run artifacts.
# ABOUTME: Covers current durability without freezing an unreleased serializer.

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


def _json_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*.json"))}


def test_read_only_resume_does_not_rewrite_current_run(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="bytes-run",
        episode_id="bytes-episode",
        world_branch_id="bytes-branch",
    )
    host = PumpStationEpisodeHost(root)
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id="bytes-action",
            decision_id=observation.decision_id,
            action_name="continue_operation",
            arguments={"reason": "Persist one current command."},
        )
    )
    before = _json_bytes(root)

    resumed = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(root),
        snapshot=run.snapshot(),
    )

    assert resumed.verify().valid
    assert _json_bytes(root) == before
