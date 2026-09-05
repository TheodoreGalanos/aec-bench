# ABOUTME: Tests current pump-station evaluation over the registered durable run.
# ABOUTME: Proves evaluation remains outside live transitions and is stable after reload.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import (
    evaluate,
    evaluate_pump_station_reference_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_controller import (
    run_pump_station_reference_controller,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
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


@pytest.mark.parametrize("calendar_late,runtime_late", [(0, 0), (-1, -1), (11, 0), (0, 7), (11, 7)])
def test_terminal_overdue_uses_each_open_obligations_own_clocks(
    tmp_path: Path, calendar_late: int, runtime_late: int
) -> None:
    from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_models import (
        PumpStationObligationStatus,
    )

    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(tmp_path / "run"),
        run_id="overdue-run",
        episode_id="overdue-episode",
        world_branch_id="overdue-branch",
    )
    state = run.state
    affected_pump_id = state.obligations[0].pump_id
    pump_a, pump_b, pump_c = (
        replace(pump, exposure=replace(pump.exposure, runtime_seconds=100 if pump.pump_id == affected_pump_id else 500))
        for pump in state.physical.pumps
    )
    state = replace(
        state,
        physical=replace(state.physical, calendar_seconds=1000, pumps=(pump_a, pump_b, pump_c)),
    )
    original = state.obligations[0]
    runtime = state.physical.pump(original.pump_id).exposure.runtime_seconds
    # Both clocks are absolute readings. An ACTIVE status alone does not prove timeliness.
    obligation = replace(
        original,
        status=PumpStationObligationStatus.ACTIVE,
        due_calendar_seconds=state.calendar_seconds - calendar_late,
        due_runtime_seconds=runtime - runtime_late,
    )
    fulfilled = replace(obligation, obligation_id="fulfilled", status=PumpStationObligationStatus.FULFILLED)
    second = replace(obligation, obligation_id="second-open")
    state = replace(state, obligations=(obligation, second, fulfilled))
    result = evaluate(
        state, run.verify(), (), manifest_content_id="a" * 64, initial_state_id=run.manifest.initial_state_id
    )
    assert result.metrics.terminal_liability.overdue_calendar_seconds == 2 * max(0, calendar_late)
    assert result.metrics.terminal_liability.overdue_affected_pump_runtime_seconds == 2 * max(0, runtime_late)


def test_terminal_physical_review_uses_current_operating_boundaries(tmp_path: Path) -> None:
    from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import PumpStationPumpMode

    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(tmp_path / "run"),
        run_id="review-run",
        episode_id="review-episode",
        world_branch_id="review-branch",
    )
    state = run.state
    physical = state.physical
    for pump in physical.pumps:
        physical = physical.with_boundary_mode(pump.pump_id, PumpStationPumpMode.SERVICE_AVAILABLE, "test-evidence")
    healthy = replace(state, physical=physical)
    report = run.verify()
    result = evaluate(healthy, report, (), manifest_content_id="a" * 64, initial_state_id=run.manifest.initial_state_id)
    assert not result.metrics.terminal_liability.review_required_physical_state
    restricted = replace(
        healthy, physical=physical.with_boundary_mode("pump-a", PumpStationPumpMode.RUN_IN_SERVICE, "test")
    )
    result = evaluate(
        restricted, report, (), manifest_content_id="a" * 64, initial_state_id=run.manifest.initial_state_id
    )
    assert result.metrics.terminal_liability.review_required_physical_state
    assert result.metrics.physical_service_review_required
    # Service shortfall remains relevant even after the closing boundary is restored.
    shortfall = replace(
        report,
        conservation=replace(
            report.conservation,
            duty=replace(
                report.conservation.duty,
                unserved_capacity_seconds=12,
            ),
        ),
    )
    result = evaluate(
        healthy, shortfall, (), manifest_content_id="a" * 64, initial_state_id=run.manifest.initial_state_id
    )
    assert not result.metrics.terminal_liability.review_required_physical_state
    assert result.metrics.physical_service_review_required
