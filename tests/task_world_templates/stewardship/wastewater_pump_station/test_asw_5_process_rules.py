# ABOUTME: Unit-tests the frozen rich-work lifecycle, dependency, and resource rules.
# ABOUTME: Covers suspension, resume, cancellation, waiver, and reservation conservation.

from __future__ import annotations

from dataclasses import replace

from rich_work_support import apply_bound, latest_process, rich_work_schedule

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    CancelProcess,
    PumpStationAuthority,
    PumpStationAuthorityOutcome,
    PumpStationDependencyKind,
    PumpStationExecutionOutcome,
    PumpStationModel,
    PumpStationProcessKind,
    PumpStationProcessStatus,
    PumpStationResourceKind,
    PumpStationSchedule,
    PumpStationState,
    PumpStationStewardshipState,
    RequestDependencyWaiver,
    RequestInspection,
    RequestObstructionClearance,
    RequestVerification,
    ResumeProcess,
    TransferDuty,
    advance_to_next_decision_point,
    create_rich_work_reference_state,
    load_reference_package,
    pump_station_model_from_package,
)


def _world() -> tuple[PumpStationModel, PumpStationStewardshipState]:
    model = pump_station_model_from_package(load_reference_package())
    state = create_rich_work_reference_state(
        model,
        schedule=rich_work_schedule(model),
    )
    return model, state


def _prepare_inspection() -> tuple[PumpStationModel, PumpStationStewardshipState]:
    model, state = _world()
    state = advance_to_next_decision_point(model, state).state
    state = apply_bound(
        model,
        state,
        TransferDuty,
        "proposal-transfer",
    ).state
    transition = apply_bound(
        model,
        state,
        RequestInspection,
        "proposal-inspection",
        pump_id="pump-b",
    )
    return model, transition.state


def _prepare_clearance() -> tuple[PumpStationModel, PumpStationStewardshipState]:
    model = pump_station_model_from_package(load_reference_package())
    inspection_duration = model.inflow.diagnostic_period_seconds
    state = create_rich_work_reference_state(
        model,
        schedule=PumpStationSchedule(
            access_available_after_seconds=0,
            repair_kit_available_after_seconds=0,
            access_withdrawal_after_seconds=inspection_duration + 1,
            access_restored_after_seconds=inspection_duration + 2,
        ),
    )
    state = advance_to_next_decision_point(model, state).state
    state = apply_bound(
        model,
        state,
        TransferDuty,
        "proposal-clearance-transfer",
    ).state
    state = apply_bound(
        model,
        state,
        RequestInspection,
        "proposal-clearance-inspection",
        pump_id="pump-b",
    ).state
    state = advance_to_next_decision_point(model, state).state
    inspection = state.latest_inspection("pump-b")
    state = apply_bound(
        model,
        state,
        RequestObstructionClearance,
        "proposal-clearance",
        pump_id="pump-b",
        inspection_evidence_id=inspection.evidence_id,
    ).state
    return model, state


def _assert_no_intervention_effect(
    before: PumpStationState,
    after: PumpStationState,
) -> None:
    assert after.duty_pump_id == before.duty_pump_id
    assert after.standby_pump_id == before.standby_pump_id
    assert after.duty_transfer_count == before.duty_transfer_count
    for pump in before.pumps:
        changed = after.pump(pump.pump_id)
        assert changed.condition.obstruction >= pump.condition.obstruction
        assert changed.condition.clearance_loss >= pump.condition.clearance_loss


def test_access_withdrawal_suspends_and_resume_uses_remaining_duration() -> None:
    model, state = _prepare_inspection()
    active = latest_process(state, PumpStationProcessKind.INSPECTION, "pump-b")
    original_duration = active.remaining_duration_seconds
    assert original_duration is not None

    suspended_transition = advance_to_next_decision_point(model, state)
    suspended = latest_process(
        suspended_transition.state,
        PumpStationProcessKind.INSPECTION,
        "pump-b",
    )

    assert suspended.status is PumpStationProcessStatus.SUSPENDED
    assert suspended.remaining_duration_seconds == original_duration - 1
    assert not {
        PumpStationResourceKind.ACCESS,
        PumpStationResourceKind.INTERVENTION_SLOT,
    } & {item.kind for item in suspended_transition.state.resource_reservations}
    _assert_no_intervention_effect(
        state.physical,
        suspended_transition.state.physical,
    )

    blocked_resume = apply_bound(
        model,
        suspended_transition.state,
        ResumeProcess,
        "proposal-resume-without-access",
        process_id=suspended.process_id,
    )
    assert blocked_resume.receipt.authority is not None
    assert blocked_resume.receipt.authority.outcome is (PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES)
    assert (
        latest_process(
            blocked_resume.state,
            PumpStationProcessKind.INSPECTION,
            "pump-b",
        ).status
        is PumpStationProcessStatus.SUSPENDED
    )

    access_returned = advance_to_next_decision_point(
        model,
        blocked_resume.state,
    ).state
    resumed_transition = apply_bound(
        model,
        access_returned,
        ResumeProcess,
        "proposal-resume",
        process_id=suspended.process_id,
    )
    resumed = latest_process(
        resumed_transition.state,
        PumpStationProcessKind.INSPECTION,
        "pump-b",
    )

    assert resumed.status is PumpStationProcessStatus.ACTIVE
    assert resumed.completion_at_seconds == (
        resumed_transition.state.physical.calendar_seconds + suspended.remaining_duration_seconds
    )
    assert {item.kind for item in resumed_transition.state.resource_reservations} == {
        PumpStationResourceKind.ACCESS,
        PumpStationResourceKind.INTERVENTION_SLOT,
    }

    completed_state = advance_to_next_decision_point(
        model,
        resumed_transition.state,
    ).state
    completed = latest_process(
        completed_state,
        PumpStationProcessKind.INSPECTION,
        "pump-b",
    )
    assert completed.status is PumpStationProcessStatus.COMPLETED
    assert completed_state.resource_reservations == ()


def test_cancellation_releases_resources_and_late_completion_has_no_effect() -> None:
    model, state = _prepare_inspection()
    process = latest_process(state, PumpStationProcessKind.INSPECTION, "pump-b")
    old_completion = next(event for event in state.scheduled_events if event.process_id == process.process_id)
    before_physical = state.physical

    cancelled_transition = apply_bound(
        model,
        state,
        CancelProcess,
        "proposal-cancel",
        process_id=process.process_id,
    )
    cancelled = latest_process(
        cancelled_transition.state,
        PumpStationProcessKind.INSPECTION,
        "pump-b",
    )

    assert cancelled_transition.receipt.execution is PumpStationExecutionOutcome.CANCELLED
    assert cancelled.status is PumpStationProcessStatus.CANCELLED
    assert cancelled_transition.state.resource_reservations == ()
    assert cancelled_transition.state.restrictions == state.restrictions
    assert cancelled_transition.state.obligations == state.obligations

    attacked = replace(
        cancelled_transition.state,
        scheduled_events=(old_completion,),
    )
    after_late_event = advance_to_next_decision_point(model, attacked).state

    assert (
        latest_process(
            after_late_event,
            PumpStationProcessKind.INSPECTION,
            "pump-b",
        ).status
        is PumpStationProcessStatus.CANCELLED
    )
    _assert_no_intervention_effect(before_physical, after_late_event.physical)


def test_clearance_suspension_keeps_kit_and_cancellation_releases_it() -> None:
    model, state = _prepare_clearance()
    clearance = latest_process(
        state,
        PumpStationProcessKind.OBSTRUCTION_CLEARANCE,
        "pump-b",
    )
    follow_up = next(iter(state.obligations))
    due_remaining = follow_up.due_calendar_seconds - state.physical.calendar_seconds

    suspended_state = advance_to_next_decision_point(model, state).state
    suspended = latest_process(
        suspended_state,
        PumpStationProcessKind.OBSTRUCTION_CLEARANCE,
        "pump-b",
    )
    suspended_follow_up = next(
        item for item in suspended_state.obligations if item.obligation_id == follow_up.obligation_id
    )
    process_reservations = {
        item.kind for item in suspended_state.resource_reservations if item.process_id == clearance.process_id
    }

    assert suspended.status is PumpStationProcessStatus.SUSPENDED
    assert process_reservations == {PumpStationResourceKind.REPAIR_KIT}
    assert suspended_follow_up.due_calendar_seconds == follow_up.due_calendar_seconds
    assert suspended_follow_up.due_calendar_seconds - suspended_state.physical.calendar_seconds == due_remaining - 1
    _assert_no_intervention_effect(state.physical, suspended_state.physical)

    cancelled_state = apply_bound(
        model,
        suspended_state,
        CancelProcess,
        "proposal-cancel-clearance",
        process_id=clearance.process_id,
    ).state

    assert not any(item.process_id == clearance.process_id for item in cancelled_state.resource_reservations)
    assert cancelled_state.resources.repair_kit_available is True
    assert cancelled_state.restrictions == suspended_state.restrictions
    assert cancelled_state.obligations == suspended_state.obligations


def test_repair_kit_is_consumed_only_after_successful_clearance() -> None:
    model, state = _prepare_clearance()
    clearance = latest_process(
        state,
        PumpStationProcessKind.OBSTRUCTION_CLEARANCE,
        "pump-b",
    )
    suspended_state = advance_to_next_decision_point(model, state).state
    restored_state = advance_to_next_decision_point(model, suspended_state).state
    resumed_state = apply_bound(
        model,
        restored_state,
        ResumeProcess,
        "proposal-resume-clearance",
        process_id=clearance.process_id,
    ).state

    assert resumed_state.resources.repair_kit_available is True
    assert any(
        item.kind is PumpStationResourceKind.REPAIR_KIT and item.process_id == clearance.process_id
        for item in resumed_state.resource_reservations
    )

    completed_state = advance_to_next_decision_point(model, resumed_state).state

    assert (
        latest_process(
            completed_state,
            PumpStationProcessKind.OBSTRUCTION_CLEARANCE,
            "pump-b",
        ).status
        is PumpStationProcessStatus.COMPLETED
    )
    assert completed_state.resources.repair_kit_available is False
    assert not any(item.kind is PumpStationResourceKind.REPAIR_KIT for item in completed_state.resource_reservations)


def test_administrative_dependency_waiver_is_narrow_and_has_no_side_effect() -> None:
    model, state = _world()
    state = advance_to_next_decision_point(model, state).state
    verification_transition = apply_bound(
        model,
        state,
        RequestVerification,
        "proposal-verification",
        pump_id="pump-a",
    )
    blocked = latest_process(
        verification_transition.state,
        PumpStationProcessKind.POST_MAINTENANCE_VERIFICATION,
        "pump-a",
    )
    dependency = next(
        item
        for item in verification_transition.state.dependencies
        if item.process_id == blocked.process_id and item.kind is PumpStationDependencyKind.ADMINISTRATIVE_CLOSEOUT
    )
    evidence = verification_transition.state.latest_functional_checks("pump-a")
    before = verification_transition.state

    waived_transition = apply_bound(
        model,
        before,
        RequestDependencyWaiver,
        "proposal-waiver",
        process_id=blocked.process_id,
        dependency_id=dependency.dependency_id,
        evidence_id=evidence.evidence_id,
    )

    assert waived_transition.receipt.authority is not None
    assert waived_transition.receipt.authority.outcome is PumpStationAuthorityOutcome.PERMITTED
    assert waived_transition.receipt.authority.required_authorities == (PumpStationAuthority.WORK_MANAGEMENT,)
    assert waived_transition.state.dependency_waivers[-1].dependency_id == (dependency.dependency_id)
    assert (
        latest_process(
            waived_transition.state,
            PumpStationProcessKind.POST_MAINTENANCE_VERIFICATION,
            "pump-a",
        ).status
        is PumpStationProcessStatus.BLOCKED
    )
    assert waived_transition.state.physical == before.physical
    assert waived_transition.state.resources == before.resources
    assert waived_transition.state.restrictions == before.restrictions
    assert waived_transition.state.obligations == before.obligations


def test_one_intervention_slot_cannot_have_two_live_reservations() -> None:
    model, state = _prepare_inspection()
    inspection = latest_process(state, PumpStationProcessKind.INSPECTION, "pump-b")

    verification_transition = apply_bound(
        model,
        state,
        RequestVerification,
        "proposal-competing-verification",
        pump_id="pump-a",
    )
    verification = latest_process(
        verification_transition.state,
        PumpStationProcessKind.POST_MAINTENANCE_VERIFICATION,
        "pump-a",
    )
    slot_reservations = tuple(
        item
        for item in verification_transition.state.resource_reservations
        if item.kind is PumpStationResourceKind.INTERVENTION_SLOT
    )

    assert verification.status is PumpStationProcessStatus.BLOCKED
    assert len(slot_reservations) == 1
    assert slot_reservations[0].process_id == inspection.process_id
