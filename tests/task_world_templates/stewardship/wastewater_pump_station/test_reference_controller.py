# ABOUTME: Proves the pump reference controller runs one canonical V4 world journey.
# ABOUTME: Covers exact snapshots, temporal access, continuity, and replay evidence.

from pathlib import Path

from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
    PUMP_STATION_REFERENCE_SYSTEM_CONTROLLER_ID,
    run_pump_station_reference_controller,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence.repository import (
    TemporalEvidenceRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSessionFactory,
)


def test_reference_controller_runs_one_canonical_v4_journey_without_a_handover_transition(
    tmp_path: Path,
) -> None:
    result = run_pump_station_reference_controller(
        repository_root=tmp_path / "run",
        run_id="reference-controller-run",
        episode_id="reference-controller-episode",
        world_branch_id="reference-controller-branch",
    )

    steps = result.run.repository.v4_steps()
    report = result.run.verify_v4()

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
    assert dict(result.semantic_outcome.evaluation.metrics)["handover_count"] == 1
    assert result.semantic_outcome.evaluation.evaluation_valid
    assert report.valid
    assert report.actor_proposals_valid
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

    recipient = PumpStationWorldSessionFactory(tmp_path / "run").open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id="reference-controller-session-day-1",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="reference-controller-tenure-day-1",
            run_id=result.end_snapshot.run_id,
            episode_id=result.end_snapshot.episode_id,
            world_branch_id=result.end_snapshot.world_branch_id,
            start_snapshot=StewardshipStateSnapshotRef(
                run_id=result.end_snapshot.run_id,
                episode_id=result.end_snapshot.episode_id,
                world_branch_id=result.end_snapshot.world_branch_id,
                sequence=result.end_snapshot.sequence,
                state_id=result.end_snapshot.state_id,
                commit_id=result.end_snapshot.commit_id,
            ),
        )
    )
    assert recipient.structured_handover is not None
    handover_receipts = TemporalEvidenceRepository(tmp_path / "run" / "temporal-evidence").retrieval_handover_receipts()
    assert len(handover_receipts) == 1
    assert recipient.retrieval_state.installed_carrier_id == handover_receipts[0].carrier_id
