# ABOUTME: Exercises the complete in-memory wastewater pump-station stewardship trajectory.
# ABOUTME: Proves provisional closure preserves run-in restriction and open verification.

from __future__ import annotations

from decimal import Decimal

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ContinueOperation,
    OperatingInterval,
    ProposalContext,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationEnvironment,
    PumpStationExecutionOutcome,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationObservationHistory,
    PumpStationProjectionContext,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    PumpStationWorkOrderStatus,
    RequestConditionalDeferral,
    RequestInspection,
    RequestObstructionClearance,
    RequestProvisionalClosure,
    RequestProvisionalReturn,
    RequestVerification,
    TransferDuty,
    advance_pump_station,
    apply_stewardship_proposal,
    bind_information_set,
    create_stewardship_state,
    initial_pump_station_state,
    load_reference_package,
    project_actor_view,
    pump_station_model_from_package,
)


def _environment() -> PumpStationEnvironment:
    return PumpStationEnvironment(
        inflow_m3_s=Decimal("0.0155"),
        wet_well_level_m=Decimal("1.65"),
        isolated=False,
    )


def _bound_context(model, state, proposal_id: str):
    package = load_reference_package()
    view = project_actor_view(
        model,
        state,
        PumpStationProjectionContext(
            episode_id="episode-reference",
            world_branch_id="branch-reference",
            actor_id="station-steward",
            agent_tenure_id="tenure-1",
            episode_started_at_seconds=0,
            tenure_started_at_seconds=0,
            projection_policy_id="pump-station-current-state-v1",
            source_artifact_ids=(
                package.package_content_id,
                package.manifest_content_id,
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
    context = ProposalContext(
        proposal_id=proposal_id,
        agent_tenure_id="tenure-1",
        based_on_sequence=state.sequence,
        base_view_id=view.view_id,
        information_set_id=information_set.information_set_id,
        reason="Reference stewardship journey.",
    )
    return context, information_set


def _apply(model, state, proposal_id, proposal_type, **parameters):
    context, information_set = _bound_context(model, state, proposal_id)
    proposal = proposal_type(context=context, **parameters)
    transition = apply_stewardship_proposal(
        model,
        state,
        proposal,
        information_set=information_set,
    )
    return transition.state, transition.receipt


def _run_reference_journey():
    model = pump_station_model_from_package(load_reference_package())
    degraded = advance_pump_station(
        model,
        initial_pump_station_state(model),
        OperatingInterval(
            elapsed_seconds=7_200_000,
            duty_runtime_seconds=7_200_000,
            duty_completed_starts=1_000,
            environment=_environment(),
        ),
    ).state
    before = degraded.pump("pump-a")
    state = create_stewardship_state(model, degraded, _environment())
    receipts = []

    state, receipt = _apply(
        model,
        state,
        "proposal-01-deferral",
        RequestConditionalDeferral,
        pump_id="pump-a",
    )
    receipts.append(receipt)
    state, receipt = _apply(
        model,
        state,
        "proposal-02-transfer",
        TransferDuty,
    )
    receipts.append(receipt)
    state, receipt = _apply(
        model,
        state,
        "proposal-03-inspection",
        RequestInspection,
        pump_id="pump-a",
    )
    receipts.append(receipt)
    state, receipt = _apply(
        model,
        state,
        "proposal-04-complete-inspection",
        ContinueOperation,
    )
    receipts.append(receipt)
    inspection = state.latest_inspection("pump-a")
    state, receipt = _apply(
        model,
        state,
        "proposal-05-wait-for-access",
        ContinueOperation,
    )
    receipts.append(receipt)
    state, receipt = _apply(
        model,
        state,
        "proposal-06-clear",
        RequestObstructionClearance,
        pump_id="pump-a",
        inspection_evidence_id=inspection.evidence_id,
    )
    receipts.append(receipt)
    state, receipt = _apply(
        model,
        state,
        "proposal-07-complete-clearance",
        ContinueOperation,
    )
    receipts.append(receipt)
    state, receipt = _apply(
        model,
        state,
        "proposal-08-functional-checks",
        ContinueOperation,
    )
    receipts.append(receipt)
    functional_checks = state.latest_functional_checks("pump-a")
    state, receipt = _apply(
        model,
        state,
        "proposal-09-return",
        RequestProvisionalReturn,
        pump_id="pump-a",
        functional_check_evidence_id=functional_checks.evidence_id,
    )
    receipts.append(receipt)
    work_order = state.work_order_for("pump-a")
    state, receipt = _apply(
        model,
        state,
        "proposal-10-close",
        RequestProvisionalClosure,
        work_order_id=work_order.work_order_id,
    )
    receipts.append(receipt)
    return model, before, state, tuple(receipts)


def test_reference_journey_closes_work_order_but_keeps_verification_open() -> None:
    _, before, state, receipts = _run_reference_journey()

    after = state.physical.pump("pump-a")
    work_order = state.work_order_for("pump-a")
    verification = state.obligation(
        PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
        "pump-a",
    )
    run_in = state.restriction(
        PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN,
        "pump-a",
    )
    deferred = state.restriction(
        PumpStationRestrictionKind.DEFERRED_PUMP_NOT_DUTY,
        "pump-a",
    )
    assert after.condition.obstruction < before.condition.obstruction
    assert after.condition.clearance_loss == before.condition.clearance_loss
    assert after.exposure == before.exposure
    assert work_order.status is PumpStationWorkOrderStatus.PROVISIONALLY_CLOSED
    assert verification.status is PumpStationObligationStatus.ACTIVE
    assert run_in.status is PumpStationRestrictionStatus.ACTIVE
    assert deferred.status is PumpStationRestrictionStatus.LIFTED
    assert receipts[-1].obligations_changed == ()
    assert receipts[-1].restrictions_changed == ()


def test_reference_journey_is_deterministic_in_memory() -> None:
    _, _, first_state, first_receipts = _run_reference_journey()
    _, _, second_state, second_receipts = _run_reference_journey()

    assert second_state == first_state
    assert second_receipts == first_receipts


def test_independent_verification_fulfils_obligation_without_lifting_run_in() -> None:
    model, _, state, _ = _run_reference_journey()
    state, scheduled = _apply(
        model,
        state,
        "proposal-11-verification",
        RequestVerification,
        pump_id="pump-a",
    )

    state, completed = _apply(
        model,
        state,
        "proposal-12-complete-verification",
        ContinueOperation,
    )

    verification = state.obligation(
        PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
        "pump-a",
    )
    run_in = state.restriction(
        PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN,
        "pump-a",
    )
    assert scheduled.execution is PumpStationExecutionOutcome.SCHEDULED
    assert completed.execution is PumpStationExecutionOutcome.COMPLETED
    assert verification.status is PumpStationObligationStatus.FULFILLED
    assert run_in.status is PumpStationRestrictionStatus.ACTIVE
    assert state.work_order_for("pump-a").status is (PumpStationWorkOrderStatus.PROVISIONALLY_CLOSED)
