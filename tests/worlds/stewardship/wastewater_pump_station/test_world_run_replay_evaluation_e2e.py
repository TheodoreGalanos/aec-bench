# ABOUTME: Proves current replay and evaluation bind the exact selected pump run.
# ABOUTME: Contains no historical proposal decoder or serializer expectation.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import (
    evaluate_pump_station_reference_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)


def test_current_evaluation_binds_the_selected_manifest_and_replay(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="evaluation-run",
        episode_id="evaluation-episode",
        world_branch_id="evaluation-branch",
    )
    host = PumpStationEpisodeHost(root)
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id="evaluation-action",
            decision_id=observation.decision_id,
            action_name="continue_operation",
            arguments={"reason": "Create current evaluation evidence."},
        )
    )

    evaluation = evaluate_pump_station_reference_run(run)

    assert evaluation.evidence.world_run_manifest_content_id == pump_station_artifact_id(run.manifest)
    assert evaluation.evidence.initial_state_id == run.manifest.initial_state_id
    assert evaluation.evidence.terminal_state_id == run.state.state_id
    assert run.verify().replay_valid
