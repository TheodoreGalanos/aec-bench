# ABOUTME: Attacks pump-station decision, evidence, continuity, and branch semantics.
# ABOUTME: Proves hostile institutional inputs cannot rewrite or contaminate world truth.

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    ContinueOperation,
    OperatingInterval,
    ProposalContext,
    PumpStationAuthority,
    PumpStationAuthorityOutcome,
    PumpStationContinuityCarrier,
    PumpStationCurrentContext,
    PumpStationEnvironment,
    PumpStationEventType,
    PumpStationEvidence,
    PumpStationEvidenceKind,
    PumpStationExecutionOutcome,
    PumpStationObligation,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationObservationHistory,
    PumpStationProcess,
    PumpStationProcessKind,
    PumpStationProcessStatus,
    PumpStationProjectionContext,
    PumpStationRestriction,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    PumpStationScheduledEvent,
    PumpStationWorkOrder,
    PumpStationWorkOrderStatus,
    RequestConditionalDeferral,
    RequestInspection,
    RequestObstructionClearance,
    RequestProvisionalReturn,
    TransferDuty,
    actor_history_entry,
    advance_pump_station,
    advance_to_next_decision_point,
    apply_stewardship_proposal,
    assess_pump_station,
    bind_information_set,
    create_stewardship_state,
    create_structured_handover,
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


def _world(*, degraded: bool = False):
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    physical = initial_pump_station_state(model)
    if degraded:
        physical = advance_pump_station(
            model,
            physical,
            OperatingInterval(
                elapsed_seconds=7_200_000,
                duty_runtime_seconds=7_200_000,
                duty_completed_starts=1_000,
                environment=_environment(),
            ),
        ).state
    state = create_stewardship_state(model, physical, _environment())
    return package, model, state


def _projection(
    package,
    state,
    *,
    branch_id: str = "branch-realised",
    tenure_id: str = "tenure-1",
) -> PumpStationProjectionContext:
    return PumpStationProjectionContext(
        episode_id="episode-asw-3a",
        world_branch_id=branch_id,
        actor_id="station-steward",
        agent_tenure_id=tenure_id,
        episode_started_at_seconds=0,
        tenure_started_at_seconds=0,
        projection_policy_id="pump-station-current-state-v1",
        source_artifact_ids=(
            package.package_content_id,
            package.manifest_content_id,
        ),
    )


def _bound(
    model,
    state,
    proposal_type,
    proposal_id: str,
    *,
    package=None,
    branch_id: str = "branch-realised",
    tenure_id: str = "tenure-1",
    carrier: PumpStationContinuityCarrier = PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
    visible_material_ids: tuple[str, ...] = (),
    history_ids: tuple[str, ...] = (),
    **parameters,
):
    selected_package = package or load_reference_package()
    view = project_actor_view(
        model,
        state,
        _projection(
            selected_package,
            state,
            branch_id=branch_id,
            tenure_id=tenure_id,
        ),
    )
    information_set = bind_information_set(
        view,
        PumpStationObservationHistory(
            agent_tenure_id=tenure_id,
            view_ids=(*history_ids, view.view_id),
        ),
        PumpStationCurrentContext(
            continuity_carrier=carrier,
            conversation_prefix_id=None,
            workspace_tool_ids=("propose-pump-station-action",),
            visible_material_ids=visible_material_ids,
        ),
    )
    proposal = proposal_type(
        context=ProposalContext(
            proposal_id=proposal_id,
            agent_tenure_id=tenure_id,
            based_on_sequence=state.sequence,
            base_view_id=view.view_id,
            information_set_id=information_set.information_set_id,
            reason="Execute one bounded world-run semantic attack.",
        ),
        **parameters,
    )
    return proposal, information_set, view


def _apply(model, state, proposal_type, proposal_id: str, **parameters):
    proposal, information_set, view = _bound(
        model,
        state,
        proposal_type,
        proposal_id,
        **parameters,
    )
    transition = apply_stewardship_proposal(
        model,
        state,
        proposal,
        information_set=information_set,
    )
    return proposal, transition, view


def test_forged_view_and_information_set_content_fail_closed() -> None:
    _, model, state = _world()
    proposal, information_set, view = _bound(
        model,
        state,
        RequestConditionalDeferral,
        "proposal-forged-binding",
        pump_id="pump-a",
    )
    forged_view = replace(
        view,
        current_state=replace(
            view.current_state,
            duty_pump_id="pump-b",
        ),
    )
    forged_view_set = replace(
        information_set,
        base_view=forged_view,
    )
    forged_context_set = replace(
        information_set,
        current_context=replace(
            information_set.current_context,
            continuity_carrier=PumpStationContinuityCarrier.STRUCTURED_HANDOVER,
            visible_material_ids=("forged-handover",),
        ),
    )

    for hostile_information_set in (forged_view_set, forged_context_set):
        transition = apply_stewardship_proposal(
            model,
            state,
            proposal,
            information_set=hostile_information_set,
        )

        assert transition.receipt.authority is not None
        assert transition.receipt.authority.outcome is PumpStationAuthorityOutcome.INVALID
        assert transition.receipt.execution is PumpStationExecutionOutcome.CANCELLED
        assert replace(transition.state, sequence=state.sequence) == state


def test_wrong_pump_and_wrong_kind_evidence_cannot_authorise_clearance() -> None:
    _, model, state = _world()
    _, inspection_requested, _ = _apply(
        model,
        state,
        RequestInspection,
        "proposal-inspect-pump-b",
        pump_id="pump-b",
    )
    _, inspection_completed, _ = _apply(
        model,
        inspection_requested.state,
        ContinueOperation,
        "proposal-complete-pump-b-inspection",
    )
    pump_b_inspection = inspection_completed.state.latest_inspection("pump-b")
    wrong_pump, information_set, _ = _bound(
        model,
        inspection_completed.state,
        RequestObstructionClearance,
        "proposal-wrong-pump-evidence",
        pump_id="pump-a",
        inspection_evidence_id=pump_b_inspection.evidence_id,
    )

    wrong_pump_result = apply_stewardship_proposal(
        model,
        inspection_completed.state,
        wrong_pump,
        information_set=information_set,
    )

    wrong_kind_evidence = PumpStationEvidence(
        evidence_id="evidence-wrong-kind",
        kind=PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
        pump_id="pump-a",
        created_at_seconds=state.physical.calendar_seconds,
        produced_by=PumpStationAuthority.MAINTENANCE,
        accepted_by=PumpStationAuthority.VERIFICATION,
        passed=True,
    )
    wrong_kind_state = replace(
        state,
        evidence=(wrong_kind_evidence,),
    )
    wrong_kind, information_set, _ = _bound(
        model,
        wrong_kind_state,
        RequestObstructionClearance,
        "proposal-wrong-kind-evidence",
        pump_id="pump-a",
        inspection_evidence_id=wrong_kind_evidence.evidence_id,
    )
    wrong_kind_result = apply_stewardship_proposal(
        model,
        wrong_kind_state,
        wrong_kind,
        information_set=information_set,
    )

    for previous, transition in (
        (inspection_completed.state, wrong_pump_result),
        (wrong_kind_state, wrong_kind_result),
    ):
        assert transition.receipt.authority is not None
        assert transition.receipt.authority.outcome is PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES
        assert transition.receipt.execution is PumpStationExecutionOutcome.CANCELLED
        assert transition.state.physical == previous.physical
        assert transition.state.processes == previous.processes


def test_same_sensor_reading_with_different_history_changes_authority() -> None:
    _, model, initial = _world()
    clean_proposal, clean_information_set, clean_view = _bound(
        model,
        initial,
        ContinueOperation,
        "proposal-clean-continue",
    )
    clean_result = apply_stewardship_proposal(
        model,
        initial,
        clean_proposal,
        information_set=clean_information_set,
    )
    _, deferral, _ = _apply(
        model,
        initial,
        RequestConditionalDeferral,
        "proposal-create-history",
        pump_id="pump-a",
    )
    blocked_proposal, blocked_information_set, blocked_view = _bound(
        model,
        deferral.state,
        ContinueOperation,
        "proposal-blocked-continue",
    )
    blocked_result = apply_stewardship_proposal(
        model,
        deferral.state,
        blocked_proposal,
        information_set=blocked_information_set,
    )
    transfer_proposal, transfer_information_set, _ = _bound(
        model,
        deferral.state,
        TransferDuty,
        "proposal-required-transfer",
    )
    transfer_result = apply_stewardship_proposal(
        model,
        deferral.state,
        transfer_proposal,
        information_set=transfer_information_set,
    )

    assert deferral.state.physical == initial.physical
    assert clean_view.current_state.observation == blocked_view.current_state.observation
    assert clean_result.receipt.authority is not None
    assert clean_result.receipt.authority.outcome is PumpStationAuthorityOutcome.PERMITTED
    assert blocked_result.receipt.authority is not None
    assert blocked_result.receipt.authority.outcome is PumpStationAuthorityOutcome.DENIED
    assert transfer_result.receipt.authority is not None
    assert transfer_result.receipt.authority.outcome is PumpStationAuthorityOutcome.PERMITTED


def test_accepted_record_cannot_rewrite_contradictory_physical_truth() -> None:
    _, model, initial = _world(degraded=True)
    assert assess_pump_station(
        model,
        initial.physical,
        initial.environment,
    ).capability.review_required
    _, deferred, _ = _apply(
        model,
        initial,
        RequestConditionalDeferral,
        "proposal-deferral-for-record-attack",
        pump_id="pump-a",
    )
    order = replace(
        deferred.state.work_order_for("pump-a"),
        status=PumpStationWorkOrderStatus.SCOPE_COMPLETED,
    )
    accepted_record = PumpStationEvidence(
        evidence_id="evidence-contradictory-functional-check",
        kind=PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
        pump_id="pump-a",
        created_at_seconds=deferred.state.physical.calendar_seconds,
        produced_by=PumpStationAuthority.MAINTENANCE,
        accepted_by=PumpStationAuthority.VERIFICATION,
        passed=True,
    )
    contradictory = replace(
        deferred.state,
        work_orders=(order,),
        evidence=(accepted_record,),
    )
    proposal, information_set, _ = _bound(
        model,
        contradictory,
        RequestProvisionalReturn,
        "proposal-accepted-record",
        pump_id="pump-a",
        functional_check_evidence_id=accepted_record.evidence_id,
    )

    transition = apply_stewardship_proposal(
        model,
        contradictory,
        proposal,
        information_set=information_set,
    )

    assert transition.receipt.authority is not None
    assert transition.receipt.authority.outcome is PumpStationAuthorityOutcome.PERMITTED
    assert transition.state.physical == contradictory.physical
    assert assess_pump_station(
        model,
        transition.state.physical,
        transition.state.environment,
    ).capability.review_required


def test_private_branch_replay_cannot_contaminate_realised_branch() -> None:
    package, model, initial = _world()
    realised_proposal, realised_information_set, _ = _bound(
        model,
        initial,
        RequestConditionalDeferral,
        "proposal-realised-deferral",
        package=package,
        branch_id="branch-realised",
        pump_id="pump-a",
    )
    private_proposal, private_information_set, _ = _bound(
        model,
        initial,
        RequestInspection,
        "proposal-private-inspection",
        package=package,
        branch_id="branch-private",
        pump_id="pump-a",
    )

    realised = apply_stewardship_proposal(
        model,
        initial,
        realised_proposal,
        information_set=realised_information_set,
    )
    private = apply_stewardship_proposal(
        model,
        initial,
        private_proposal,
        information_set=private_information_set,
    )
    realised_view = project_actor_view(
        model,
        realised.state,
        _projection(
            package,
            realised.state,
            branch_id="branch-realised",
        ),
    )

    assert initial.restrictions == ()
    assert initial.processes == ()
    assert realised.state.processes == ()
    assert private.state.restrictions == ()
    assert realised_view.world_branch_id == "branch-realised"
    assert "branch-private" not in repr(realised_view)
    assert private_proposal.context.proposal_id not in repr(realised_view)
    assert private.state.processes[0].process_id not in repr(realised_view)


def test_current_view_and_structured_handover_preserve_present_duty_semantics() -> None:
    package, model, initial = _world()
    deferral_proposal, deferral_information_set, _ = _bound(
        model,
        initial,
        RequestConditionalDeferral,
        "proposal-carrier-deferral",
        package=package,
        tenure_id="tenure-1",
        pump_id="pump-a",
    )
    deferral = apply_stewardship_proposal(
        model,
        initial,
        deferral_proposal,
        information_set=deferral_information_set,
    )
    recipient_view = project_actor_view(
        model,
        deferral.state,
        _projection(
            package,
            deferral.state,
            tenure_id="tenure-2",
        ),
    )
    handover = create_structured_handover(
        recipient_view,
        from_tenure_id="tenure-1",
        history=(actor_history_entry(deferral, deferral_proposal),),
        maximum_history_entries=8,
    )
    current_proposal, current_information_set, current_view = _bound(
        model,
        deferral.state,
        TransferDuty,
        "proposal-current-carrier",
        package=package,
        tenure_id="tenure-2",
    )
    handover_proposal, handover_information_set, handover_view = _bound(
        model,
        deferral.state,
        TransferDuty,
        "proposal-handover-carrier",
        package=package,
        tenure_id="tenure-2",
        carrier=PumpStationContinuityCarrier.STRUCTURED_HANDOVER,
        visible_material_ids=(handover.handover_id,),
    )

    current_result = apply_stewardship_proposal(
        model,
        deferral.state,
        current_proposal,
        information_set=current_information_set,
    )
    handover_result = apply_stewardship_proposal(
        model,
        deferral.state,
        handover_proposal,
        information_set=handover_information_set,
    )

    assert current_view.current_state == handover_view.current_state
    assert current_information_set.information_set_id != handover_information_set.information_set_id
    assert current_result.state == handover_result.state
    assert current_result.receipt.authority == handover_result.receipt.authority
    assert current_result.receipt.execution == handover_result.receipt.execution
    assert current_result.receipt.physical_change == handover_result.receipt.physical_change


def test_failed_verification_preserves_restriction_and_open_obligation() -> None:
    _, model, initial = _world(degraded=True)
    now = initial.physical.calendar_seconds
    restriction = PumpStationRestriction(
        restriction_id="restriction-run-in",
        kind=PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN,
        pump_id="pump-a",
        status=PumpStationRestrictionStatus.ACTIVE,
        created_sequence=0,
    )
    obligation = PumpStationObligation(
        obligation_id="obligation-verification",
        kind=PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
        pump_id="pump-a",
        status=PumpStationObligationStatus.ACTIVE,
        originating_proposal_id="proposal-provisional-return",
        responsible_authority=PumpStationAuthority.VERIFICATION,
        linked_restriction_id=restriction.restriction_id,
        due_calendar_seconds=now + model.inflow.diagnostic_period_seconds,
        due_runtime_seconds=(
            initial.physical.pump("pump-a").exposure.runtime_seconds + model.inflow.diagnostic_period_seconds
        ),
        created_sequence=0,
    )
    work_order = PumpStationWorkOrder(
        work_order_id="work-order-pump-a",
        pump_id="pump-a",
        status=PumpStationWorkOrderStatus.PROVISIONALLY_CLOSED,
        created_sequence=0,
    )
    process = PumpStationProcess(
        process_id="process-verification",
        kind=PumpStationProcessKind.POST_MAINTENANCE_VERIFICATION,
        pump_id="pump-a",
        work_order_id=work_order.work_order_id,
        status=PumpStationProcessStatus.IN_PROGRESS,
        started_at_seconds=now,
        completion_at_seconds=now,
        performer=PumpStationAuthority.VERIFICATION,
    )
    event = PumpStationScheduledEvent(
        event_id="event-verification-completion",
        event_type=PumpStationEventType.PROCESS_COMPLETION,
        scheduled_seconds=now,
        process_id=process.process_id,
    )
    attacked = replace(
        initial,
        restrictions=(restriction,),
        obligations=(obligation,),
        work_orders=(work_order,),
        processes=(process,),
        scheduled_events=(event,),
    )

    failed = advance_to_next_decision_point(model, attacked)

    assert failed.receipt.execution is PumpStationExecutionOutcome.FAILED
    assert failed.state.physical == attacked.physical
    assert failed.state.processes[0].status is PumpStationProcessStatus.FAILED
    assert failed.state.obligations[0].status is PumpStationObligationStatus.ACTIVE
    assert failed.state.restrictions[0].status is PumpStationRestrictionStatus.ACTIVE
    assert failed.state.work_orders[0].status is PumpStationWorkOrderStatus.OPEN
    assert failed.state.evidence[-1].passed is False
