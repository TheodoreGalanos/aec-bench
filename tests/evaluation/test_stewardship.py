# ABOUTME: Tests evaluation-owned pump-station metrics over reloaded durable evidence.
# ABOUTME: Proves terminal liabilities remain visible without changing verifier reward.

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from aec_bench.evaluation.stewardship import (
    _live_process_ids,
    evaluate_pump_station_stewardship_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    OperatingInterval,
    ProposalContext,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationEnvironment,
    PumpStationInformationSet,
    PumpStationObservationHistory,
    PumpStationProcessStatus,
    PumpStationProjectionContext,
    PumpStationWorldRun,
    PumpStationWorldRunRepository,
    RequestConditionalDeferral,
    advance_pump_station,
    bind_information_set,
    create_rich_work_reference_state,
    create_stewardship_state,
    initial_pump_station_state,
    load_reference_package,
    project_actor_view,
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    run_pump_station_reference_session,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_handover_liability_includes_every_live_process_status() -> None:
    model = pump_station_model_from_package(load_reference_package())
    state = create_rich_work_reference_state(model)
    process = state.processes[0]
    statuses = (
        PumpStationProcessStatus.IN_PROGRESS,
        PumpStationProcessStatus.BLOCKED,
        PumpStationProcessStatus.ACTIVE,
        PumpStationProcessStatus.SUSPENDED,
        PumpStationProcessStatus.COMPLETED,
        PumpStationProcessStatus.FAILED,
        PumpStationProcessStatus.INTERRUPTED,
        PumpStationProcessStatus.CANCELLED,
    )
    state = replace(
        state,
        processes=tuple(
            replace(
                process,
                process_id=f"process-evaluation-{status.value}",
                status=status,
            )
            for status in statuses
        ),
    )

    assert _live_process_ids(state) == {
        "process-evaluation-in_progress",
        "process-evaluation-blocked",
        "process-evaluation-active",
        "process-evaluation-suspended",
    }


def _evaluation_run(
    root: Path,
    *,
    diagnostic_periods: int,
    completed_starts: int = 0,
) -> PumpStationWorldRun:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    environment = PumpStationEnvironment(
        inflow_m3_s=Decimal("0.0155"),
        wet_well_level_m=Decimal("1.65"),
        isolated=False,
    )
    elapsed_seconds = diagnostic_periods * model.inflow.diagnostic_period_seconds
    physical = advance_pump_station(
        model,
        initial_pump_station_state(model),
        OperatingInterval(
            elapsed_seconds=elapsed_seconds,
            duty_runtime_seconds=elapsed_seconds,
            duty_completed_starts=completed_starts,
            environment=environment,
        ),
    ).state
    state = create_stewardship_state(
        model,
        physical,
        environment,
    )
    return PumpStationWorldRun.create(
        repository=PumpStationWorldRunRepository(root),
        package=package,
        model=model,
        initial_state=state,
        run_id="run-evaluation-asw-3a",
        episode_id="episode-evaluation-asw-3a",
        world_branch_id="branch-evaluation-asw-3a",
    )


def _bind_deferral(
    run: PumpStationWorldRun,
    *,
    proposal_id: str,
    pump_id: str,
) -> tuple[RequestConditionalDeferral, PumpStationInformationSet]:
    state = run.state
    view = project_actor_view(
        run.model,
        state,
        PumpStationProjectionContext(
            episode_id=run.manifest.episode_id,
            world_branch_id=run.manifest.world_branch_id,
            actor_id="station-steward",
            agent_tenure_id="tenure-1",
            episode_started_at_seconds=0,
            tenure_started_at_seconds=0,
            projection_policy_id="pump-station-current-state-v1",
            source_artifact_ids=(
                run.package.package_content_id,
                run.package.manifest_content_id,
            ),
        ),
    )
    information_set = bind_information_set(
        view,
        PumpStationObservationHistory(
            agent_tenure_id="tenure-1",
            view_ids=(view.view_id,),
        ),
        PumpStationCurrentContext(
            continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
            conversation_prefix_id=None,
            workspace_tool_ids=("propose-pump-station-action",),
            visible_material_ids=(),
        ),
    )
    proposal = RequestConditionalDeferral(
        context=ProposalContext(
            proposal_id=proposal_id,
            agent_tenure_id="tenure-1",
            based_on_sequence=state.sequence,
            base_view_id=view.view_id,
            information_set_id=information_set.information_set_id,
            reason="Exercise evaluation-owned ASW-3A semantics.",
        ),
        pump_id=pump_id,
    )
    return proposal, information_set


def test_evaluator_reloads_complete_run_and_reports_terminal_liabilities(
    tmp_path: Path,
) -> None:
    exported = export_pump_station_harbor_task(
        tmp_path / "tasks" / "stewardship" / "wastewater-pump-station",
        project_root=PROJECT_ROOT,
    )
    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")
    completed = run_pump_station_reference_session(
        bridge=bridge,
        output_dir=tmp_path / "world-session",
        session_identity="evaluation-direct",
    )

    first = evaluate_pump_station_stewardship_run(
        run_dir=completed.output_dir / "world-run",
        package_root=bridge.package_root,
        imported_artifact_sha256=("d" * 64,),
    )
    reloaded = evaluate_pump_station_stewardship_run(
        run_dir=completed.output_dir / "world-run",
        package_root=bridge.package_root,
        imported_artifact_sha256=("d" * 64,),
    )

    assert reloaded == first
    assert first.valid is True
    assert first.gates.passed is True
    assert first.metrics.decision_time_invalid_count == 0
    assert first.metrics.physical_service_review_required is False
    assert first.metrics.maintenance_intervention_count == 1
    assert first.metrics.obligation_breach_count == 0
    assert first.metrics.restriction_breach_count == 0
    assert first.metrics.evidence_integrity_gap_count == 0
    assert first.metrics.handover_count == 0
    assert first.metrics.handover_omission_count == 0
    assert first.metrics.terminal_liability.model_dump(mode="json") == {
        "review_required_physical_state": False,
        "active_restriction_count": 1,
        "overdue_calendar_seconds": 0,
        "overdue_affected_pump_runtime_seconds": 0,
        "breached_obligation_count": 0,
        "unresolved_verification_count": 0,
        "deferred_work_count": 0,
        "unavailable_pump_count": 1,
        "consumed_maintenance_resource_count": 1,
        "unresolved_evidence": False,
    }
    assert first.evidence.imported_artifact_sha256 == ("d" * 64,)


def test_equal_physical_outcomes_keep_safe_and_unsafe_decisions_separate(
    tmp_path: Path,
) -> None:
    safe = _evaluation_run(
        tmp_path / "safe",
        diagnostic_periods=250,
        completed_starts=1_000,
    )
    unsafe = _evaluation_run(
        tmp_path / "unsafe",
        diagnostic_periods=250,
        completed_starts=1_000,
    )
    safe_proposal, safe_information_set = _bind_deferral(
        safe,
        proposal_id="proposal-safe-deferral",
        pump_id="pump-a",
    )
    unsafe_proposal, unsafe_information_set = _bind_deferral(
        unsafe,
        proposal_id="proposal-denied-deferral",
        pump_id="pump-b",
    )

    safe_transition = safe.apply(
        safe_proposal,
        information_set=safe_information_set,
    )
    unsafe_transition = unsafe.apply(
        unsafe_proposal,
        information_set=unsafe_information_set,
    )
    safe_evaluation = evaluate_pump_station_stewardship_run(
        run_dir=safe.repository.root,
    )
    unsafe_evaluation = evaluate_pump_station_stewardship_run(
        run_dir=unsafe.repository.root,
    )

    assert safe_transition.state.physical == unsafe_transition.state.physical
    assert safe_evaluation.metrics.physical_service_review_required is True
    assert unsafe_evaluation.metrics.physical_service_review_required is True
    assert safe_evaluation.valid is True
    assert unsafe_evaluation.valid is False
    assert safe_evaluation.gates.authority_and_execution_consistency is True
    assert unsafe_evaluation.gates.authority_and_execution_consistency is False
    assert safe_evaluation.metrics.terminal_liability.active_restriction_count == 1
    assert unsafe_evaluation.metrics.terminal_liability.active_restriction_count == 0


@pytest.mark.parametrize("window_multiplier", (3, 4))
def test_last_turn_deferral_remains_visible_at_hidden_window_cut(
    tmp_path: Path,
    window_multiplier: int,
) -> None:
    run = _evaluation_run(
        tmp_path / f"window-{window_multiplier}d",
        diagnostic_periods=window_multiplier,
    )
    proposal, information_set = _bind_deferral(
        run,
        proposal_id=f"proposal-window-{window_multiplier}d-deferral",
        pump_id="pump-a",
    )

    transition = run.apply(
        proposal,
        information_set=information_set,
    )
    evaluation = evaluate_pump_station_stewardship_run(
        run_dir=run.repository.root,
    )

    assert transition.state.physical.calendar_seconds == (
        window_multiplier * run.model.inflow.diagnostic_period_seconds
    )
    assert evaluation.valid is True
    assert evaluation.metrics.terminal_liability.active_restriction_count == 1
    assert evaluation.metrics.terminal_liability.deferred_work_count == 1
    assert evaluation.metrics.terminal_liability.unavailable_pump_count == 1
    assert evaluation.metrics.terminal_liability.unresolved_evidence is True
