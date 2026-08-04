# ABOUTME: Proves the pump reference controller runs one canonical current world journey.
# ABOUTME: Covers exact snapshots, temporal access, opaque decisions, and replay evidence.

from pathlib import Path

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    run_pump_station_reference_controller,
)


def test_reference_controller_runs_one_canonical_journey_without_a_handover_transition(
    tmp_path: Path,
) -> None:
    result = run_pump_station_reference_controller(
        repository_root=tmp_path / "run",
        run_id="reference-controller-run",
        episode_id="reference-controller-episode",
        world_branch_id="reference-controller-branch",
    )

    steps = result.run.repository.command_steps()
    report = result.run.verify()

    assert result.controller_id == PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID
    assert result.start_snapshot.sequence == 0
    assert result.end_snapshot == result.run.snapshot()
    assert result.end_snapshot.sequence == 25
    assert len(steps) == 25
    assert all(step.command.kind != "handover" for step in steps)
    assert result.temporal_access == (
        ("search_evidence", "NO_ACCESSIBLE_RESULT", ()),
        ("search_evidence", "OK", ("pump-c-collateral-inspection-note.v1",)),
        ("fetch_evidence", "OK", ("pump-c-collateral-inspection-note.v1",)),
    )
    assert result.semantic_outcome.temporal_access == result.temporal_access
    assert len(result.semantic_outcome.ordered_actions) == 25
    assert result.semantic_outcome.terminal_state.calendar_seconds == 223_200
    assert dict(result.semantic_outcome.evaluation.metrics)["handover_count"] == 0
    assert result.semantic_outcome.evaluation.evaluation_valid
    assert report.valid
    assert report.actor_actions_valid
    assert report.host_controls_valid
    assert report.conservation.valid
    assert len(report.conservation.work.opening_ids) == 2
    assert len(report.conservation.work.generated_ids) == 4
    assert len(report.conservation.work.terminal_ids) == 5
    assert len(report.conservation.work.closing_ids) == 1
    assert len(report.conservation.liabilities.opening_ids) == 2
    assert len(report.conservation.liabilities.created_ids) == 3
    assert len(report.conservation.liabilities.discharged_ids) == 4
    assert len(report.conservation.liabilities.closing_ids) == 1
    assert report.replayed_transition_ids == tuple(step.transition.receipt.transition_id for step in steps)
