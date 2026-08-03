# ABOUTME: Tests current pump-station evaluation over the registered durable run.
# ABOUTME: Proves evaluation remains outside live transitions and is stable after reload.

from __future__ import annotations

from pathlib import Path

from aec_bench.evaluation.stewardship import evaluate_pump_station_reference_run
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
    run_pump_station_reference_controller,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def test_current_evaluation_is_stable_after_durable_reload(tmp_path: Path) -> None:
    root = tmp_path / "world-run"
    completed = run_pump_station_reference_controller(
        root,
        "evaluation-run",
        "evaluation-episode",
        "evaluation-branch",
    )
    first = evaluate_pump_station_reference_run(completed.run)
    repository = PumpStationWorldRunRepository(root)
    reloaded = PumpStationWorldRun.resume_reference_system(
        repository=repository,
        snapshot=repository.current_snapshot(),
    )

    assert evaluate_pump_station_reference_run(reloaded) == first
    assert first.evidence.initial_state_id == completed.run.manifest.initial_state_id
    assert first.evidence.terminal_state_id == completed.run.state.state_id
    assert first.gates.artifact_and_replay_integrity
