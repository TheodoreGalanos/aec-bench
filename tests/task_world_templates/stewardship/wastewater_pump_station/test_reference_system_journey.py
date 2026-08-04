# ABOUTME: Runs the complete ASW-8 Day 0 to Day 2 reference journey through closed actions.
# ABOUTME: Checks explicit Operations reviews, exact work generation, and the declared terminal state.

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCoupledWorldError,
    PumpStationCoupledWorldState,
    apply_common_boundary_control,
    apply_coupled_actor_action,
    apply_operations_boundary_review,
    apply_process_outcome,
    create_asw_8_world_state,
    project_coupled_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationAvailabilityInterval,
    PumpStationBacklogItem,
    PumpStationBacklogStatus,
    PumpStationConsumablePool,
    PumpStationCoupledProcessStatus,
    PumpStationPriority,
    PumpStationReusablePool,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationPumpMode,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationCommonBoundaryRequest,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
)


def _act(
    state: PumpStationCoupledWorldState,
    request_id: str,
    action_name: str,
    **arguments: object,
) -> PumpStationCoupledWorldState:
    return apply_coupled_actor_action(
        state,
        request_id=request_id,
        action_name=action_name,
        arguments={"reason": f"Complete {request_id} under the visible service plan.", **arguments},
    ).state


def _continue_to(state: PumpStationCoupledWorldState, target: int) -> PumpStationCoupledWorldState:
    while state.calendar_seconds < target:
        state = _act(
            state,
            f"continue-{state.sequence + 1}",
            "continue_operation",
        )
    assert state.calendar_seconds == target
    return state


def _item_id(state: PumpStationCoupledWorldState, rule: str, target: str) -> str:
    matching = tuple(
        item.item_id
        for item in state.backlog
        if item.generation_rule_id == rule
        and item.target_id == target
        and item.status in {PumpStationBacklogStatus.OPEN, PumpStationBacklogStatus.PLANNED}
    )
    assert len(matching) == 1
    return matching[0]


def _review(
    state: PumpStationCoupledWorldState,
    *,
    review_id: str,
    kind: str,
    pump_id: str,
    restriction_id: str,
    evidence_id: str,
) -> PumpStationCoupledWorldState:
    return apply_operations_boundary_review(
        state,
        PumpStationOperationsBoundaryReviewRequest(
            review_id=review_id,
            review_kind=kind,
            pump_id=pump_id,
            restriction_or_isolation_permit_id=restriction_id,
            accepted_evidence_id=evidence_id,
            requested_outcome="release",
            base_state_id=state.state_id,
            operations_authority_id="operations-controller",
            reason="Release the matched boundary after accepted evidence.",
        ),
    ).state


def _set_power_boundary(
    state: PumpStationCoupledWorldState,
    request_id: str,
    *,
    available: bool,
) -> PumpStationCoupledWorldState:
    return apply_common_boundary_control(
        state,
        PumpStationCommonBoundaryRequest(
            request_id=request_id,
            authority_id="operations-controller",
            boundary_kind="power",
            available=available,
            base_state_id=state.state_id,
        ),
    ).state


def _runtime_backlog(item_id: str, pump_id: str, runtime_limit: int) -> PumpStationBacklogItem:
    return PumpStationBacklogItem(
        item_id=item_id,
        work_type="post_maintenance_verification",
        target_kind="asset",
        target_id=pump_id,
        generation_rule_id="WG-04" if pump_id == "pump-a" else "WG-07",
        generation_ordinal=1,
        originating_record_id=f"{item_id}-source",
        linked_obligation_ids=(),
        linked_restriction_ids=(),
        linked_work_order_id=None,
        linked_process_id=None,
        generated_at_calendar_seconds=64_800,
        base_priority=PumpStationPriority.P3,
        effective_priority=PumpStationPriority.P3,
        due_calendar_seconds=None,
        due_runtime_clock_kind="pump_total",
        due_runtime_clock_id=pump_id,
        due_runtime_limit_seconds=runtime_limit,
        status=PumpStationBacklogStatus.PLANNED,
        blocked_from_status=None,
        blocked_since_calendar_seconds=None,
        accumulated_blocked_seconds=0,
        closure_rule="accepted verification",
        closure_evidence_ids=(),
        supersedes_item_id=None,
        superseded_by_item_id=None,
    )


def test_current_projection_presents_dates_and_complete_planning_windows() -> None:
    view = project_coupled_actor_view(create_asw_8_world_state())

    assert view.time_zone == "Australia/Sydney"
    assert view.current_datetime == "2026-01-01T06:00:00+11:00"
    assert view.service_schedule_disclosed_through_datetime == "2026-01-03T15:00:00+11:00"
    assert view.resource_schedule_disclosed_through_datetime == "2026-01-03T15:00:00+11:00"
    assert view.service_schedule_local[0] == (
        "2026-01-01T06:00:00+11:00",
        "2026-01-01T18:00:00+11:00",
        1,
    )
    access = next(item for item in view.resource_availability_local if item[0] == "field-access-slot")
    assert access[1][-1] == (
        "2026-01-03T06:00:00+11:00",
        "2026-01-03T15:00:00+11:00",
    )
    assert view.pump_runtime_display == (
        ("pump-a", "1 operating hour"),
        ("pump-b", "0 operating hours"),
        ("pump-c", "0 operating hours"),
    )
    assert view.evidence_health == (
        ("initial-b-inspection-accepted", "pump-b", "current", True),
        ("initial-c-assurance-accepted", "pump-c", "current", True),
    )


def run_reference_journey() -> PumpStationCoupledWorldState:
    state = create_asw_8_world_state()
    state = _act(
        state,
        "a-verification",
        "request_post_maintenance_verification",
        pump_id="pump-a",
        backlog_item_id="backlog-a-verification-001",
    )
    state = _continue_to(state, 50_400)
    assert state.physical.boundary("pump-a").mode is PumpStationPumpMode.RUN_IN_SERVICE
    assert not state.physical.availability("pump-a").assured_for_outage_planning
    state = _review(
        state,
        review_id="operations-review-a-001",
        kind="post_verification_restriction",
        pump_id="pump-a",
        restriction_id="restriction-a-run-in-001",
        evidence_id="evidence-pump-a-verification-pass-001",
    )
    state = _continue_to(state, 64_800)
    state = _act(
        state,
        "assign-a-c",
        "request_duty_assignment",
        ordered_pump_ids=["pump-a", "pump-c"],
    )
    state = _continue_to(state, 93_600)
    assert _item_id(state, "WG-07", "pump-c")
    state = _continue_to(state, 100_800)
    assert state.event_effect_ids[-1] == "document-review-point-c-001"
    state = _continue_to(state, 108_000)
    state = _act(
        state,
        "b-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    state = _continue_to(state, 122_400)
    assert state.physical.boundary("pump-b").mode is PumpStationPumpMode.TEST_ONLY
    functional_id = _item_id(state, "WG-03", "pump-b")
    state = _act(
        state,
        "b-functional",
        "request_functional_check",
        pump_id="pump-b",
        backlog_item_id=functional_id,
    )
    state = _continue_to(state, 126_000)
    assert state.physical.test_running_pump_ids == ()
    assert state.physical.pump("pump-b").condition.obstruction == Decimal("0.10539999999998400")
    state = _act(
        state,
        "b-provisional-return",
        "request_provisional_return",
        pump_id="pump-b",
        functional_check_evidence_id="evidence-b-functional-check-pass-001",
    )
    state = _act(
        state,
        "b-provisional-closure",
        "request_provisional_closure",
        work_order_id="work-order-b-001",
    )
    verification_id = _item_id(state, "WG-04", "pump-b")
    view = project_coupled_actor_view(state)
    assert view.ranked_backlog[0].generation_rule_id == "WG-07"
    state = _act(
        state,
        "b-verification",
        "request_post_maintenance_verification",
        pump_id="pump-b",
        backlog_item_id=verification_id,
    )
    state = _continue_to(state, 154_800)
    assert state.physical.boundary("pump-b").mode is PumpStationPumpMode.RUN_IN_SERVICE
    state = _review(
        state,
        review_id="operations-review-b-001",
        kind="post_verification_restriction",
        pump_id="pump-b",
        restriction_id="restriction-pump-b-run-in-001",
        evidence_id="evidence-pump-b-verification-pass-001",
    )
    state = _continue_to(state, 194_400)
    state = _act(
        state,
        "assign-a-b",
        "request_duty_assignment",
        ordered_pump_ids=["pump-a", "pump-b"],
    )
    c_item_id = _item_id(state, "WG-07", "pump-c")
    state = _act(
        state,
        "c-inspection",
        "request_inspection",
        pump_id="pump-c",
        backlog_item_id=c_item_id,
    )
    state = _continue_to(state, 223_200)
    assert state.physical.pump("pump-c").condition.obstruction == Decimal("0.00514999999968000")
    assert state.physical.pump("pump-c").condition.clearance_loss == Decimal("0.00239999999976000")
    state = _review(
        state,
        review_id="operations-review-c-001",
        kind="post_inspection_isolation",
        pump_id="pump-c",
        restriction_id="isolation-pump-c-c-inspection",
        evidence_id="evidence-c-inspection-no-finding-001",
    )
    return state


def test_complete_reference_journey_reaches_declared_terminal_state() -> None:
    state = run_reference_journey()
    view = project_coupled_actor_view(state)

    assert state.calendar_seconds == 223_200
    assert state.assignment.ordered_pump_ids == ("pump-a", "pump-b")
    assert state.physical.service_running_pump_ids == ("pump-a",)
    assert state.physical.test_running_pump_ids == ()
    assert all(boundary.mode is PumpStationPumpMode.SERVICE_AVAILABLE for boundary in view.pump_boundaries)
    assert all(availability.assured_for_outage_planning for availability in view.pump_availability)
    assert state.active_restriction_ids == ()
    assert len(state.terminal_work_item_ids) == 5
    open_items = tuple(item for item in state.backlog if item.status is PumpStationBacklogStatus.PLANNED)
    assert len(open_items) == 1
    assert open_items[0].generation_rule_id == "WG-06"
    kit = state.resources.pool("obstruction-clearance-kit")
    assert isinstance(kit, PumpStationConsumablePool)
    assert kit.on_hand == 0
    assert state.active_liability_ids == (open_items[0].item_id,)
    assert len(state.created_liability_ids) == 3
    assert len(state.discharged_liability_ids) == 4


def test_operations_review_rejects_stale_or_mismatched_input() -> None:
    state = create_asw_8_world_state()
    state = _act(
        state,
        "a-verification",
        "request_post_maintenance_verification",
        pump_id="pump-a",
        backlog_item_id="backlog-a-verification-001",
    )
    state = _continue_to(state, 50_400)
    bad = PumpStationOperationsBoundaryReviewRequest(
        review_id="bad-review",
        review_kind="post_verification_restriction",
        pump_id="pump-b",
        restriction_or_isolation_permit_id="restriction-a-run-in-001",
        accepted_evidence_id="evidence-pump-a-verification-pass-001",
        requested_outcome="release",
        base_state_id="stale-state",
        operations_authority_id="operations-controller",
        reason="This input is intentionally stale.",
    )

    with pytest.raises(PumpStationCoupledWorldError) as raised:
        apply_operations_boundary_review(state, bad)

    assert raised.value.code == "stale-operations-review"
    assert state.physical.boundary("pump-a").mode is PumpStationPumpMode.RUN_IN_SERVICE

    wrong_evidence = replace(
        bad,
        review_id="wrong-evidence-review",
        pump_id="pump-a",
        accepted_evidence_id="initial-c-assurance-accepted",
        base_state_id=state.state_id,
    )
    with pytest.raises(PumpStationCoupledWorldError) as wrong_evidence_error:
        apply_operations_boundary_review(state, wrong_evidence)

    assert wrong_evidence_error.value.code == "operations-review-evidence-binding"
    assert state.physical.boundary("pump-a").mode is PumpStationPumpMode.RUN_IN_SERVICE

    denied = replace(
        wrong_evidence,
        review_id="denied-review",
        accepted_evidence_id="evidence-pump-a-verification-pass-001",
        requested_outcome="deny",
    )
    with pytest.raises(PumpStationCoupledWorldError) as denied_error:
        apply_operations_boundary_review(state, denied)
    assert denied_error.value.code == "operations-review-outcome"

    wrong_restriction = replace(
        denied,
        review_id="wrong-restriction-review",
        restriction_or_isolation_permit_id="restriction-b-isolated-001",
        requested_outcome="release",
    )
    with pytest.raises(PumpStationCoupledWorldError) as restriction_error:
        apply_operations_boundary_review(state, wrong_restriction)
    assert restriction_error.value.code == "operations-review-mismatch"

    missing_evidence = replace(
        wrong_restriction,
        review_id="missing-evidence-review",
        restriction_or_isolation_permit_id="restriction-a-run-in-001",
        accepted_evidence_id="missing-evidence",
    )
    with pytest.raises(PumpStationCoupledWorldError) as missing_evidence_error:
        apply_operations_boundary_review(state, missing_evidence)
    assert missing_evidence_error.value.code == "operations-review-evidence"
    assert state.physical.boundary("pump-a").mode is PumpStationPumpMode.RUN_IN_SERVICE


def test_power_stop_suspends_clearance_and_resume_uses_remaining_duration() -> None:
    state = create_asw_8_world_state()
    state = _act(
        state,
        "late-b-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    process_id = state.processes[-1].process_id

    state = _set_power_boundary(state, "suspending-power-stop", available=False)
    process = next(value for value in state.processes if value.process_id == process_id)

    assert process.status is PumpStationCoupledProcessStatus.SUSPENDED
    assert process.remaining_duration_seconds == 14_400

    state = _set_power_boundary(state, "suspending-power-restore", available=True)
    state = _act(state, "resume-b-clearance", "resume_process", process_id=process_id)
    resumed = next(value for value in state.processes if value.process_id == process_id)
    assert resumed.due_at_calendar_seconds == 36_000

    state = _act(state, "complete-resumed-clearance", "continue_operation")
    completed = next(value for value in state.processes if value.process_id == process_id)
    assert state.calendar_seconds == 36_000
    assert completed.status is PumpStationCoupledProcessStatus.COMPLETED


def test_resource_withdrawal_wins_over_same_time_process_completion() -> None:
    state = create_asw_8_world_state()
    state = replace(
        state,
        physical=replace(state.physical, calendar_seconds=46_800),
    )
    opening_obstruction = state.physical.pump("pump-b").condition.obstruction
    state = _act(
        state,
        "same-time-b-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )

    state = _act(state, "continue-to-withdrawal", "continue_operation")

    process = state.processes[-1]
    assert state.calendar_seconds == 61_200
    assert process.status is PumpStationCoupledProcessStatus.SUSPENDED
    assert state.backlog_item("backlog-b-clearance-001").status is PumpStationBacklogStatus.BLOCKED
    assert state.physical.pump("pump-b").condition.obstruction == opening_obstruction


def test_field_process_start_and_resume_recheck_visible_assured_capacity() -> None:
    extended_window = (PumpStationAvailabilityInterval(21_600, 93_600),)

    def at_capacity_boundary(state: PumpStationCoupledWorldState) -> PumpStationCoupledWorldState:
        resources = replace(
            state.resources,
            pools=tuple(
                replace(pool, availability_intervals=extended_window)
                if isinstance(pool, PumpStationReusablePool)
                else pool
                for pool in state.resources.pools
            ),
        )
        return replace(
            state,
            physical=replace(state.physical, calendar_seconds=60_000),
            resources=resources,
        )

    start = at_capacity_boundary(create_asw_8_world_state())
    with pytest.raises(PumpStationCoupledWorldError, match="planned-outage-capacity"):
        _act(
            start,
            "capacity-blocked-start",
            "request_obstruction_clearance",
            pump_id="pump-b",
            backlog_item_id="backlog-b-clearance-001",
            inspection_evidence_id="initial-b-inspection-accepted",
        )

    resume = create_asw_8_world_state()
    resume = _act(
        resume,
        "capacity-resume-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    process_id = resume.processes[-1].process_id
    resume = _set_power_boundary(resume, "capacity-resume-stop", available=False)
    resume = at_capacity_boundary(resume)
    resume = replace(
        resume,
        physical=replace(
            resume.physical,
            common_boundary=replace(resume.physical.common_boundary, power_available=True),
        ),
    )

    with pytest.raises(PumpStationCoupledWorldError, match="planned-outage-capacity"):
        _act(resume, "capacity-blocked-resume", "resume_process", process_id=process_id)


def test_cancel_after_suspension_replans_work_and_releases_the_consumable() -> None:
    state = create_asw_8_world_state()
    state = _act(
        state,
        "cancel-clearance-start",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    process_id = state.processes[-1].process_id
    state = _set_power_boundary(state, "cancel-clearance-stop", available=False)
    state = _act(state, "cancel-b-clearance", "cancel_process", process_id=process_id)

    item = state.backlog_item("backlog-b-clearance-001")
    kit = state.resources.pool("obstruction-clearance-kit")
    assert item.status is PumpStationBacklogStatus.PLANNED
    assert item.linked_process_id is None
    assert kit.free == 1
    assert kit.reserved == 0


def test_failed_functional_check_retains_work_and_failed_verification_creates_rework() -> None:
    functional = create_asw_8_world_state()
    functional = _act(
        functional,
        "failed-functional-clearance",
        "request_obstruction_clearance",
        pump_id="pump-b",
        backlog_item_id="backlog-b-clearance-001",
        inspection_evidence_id="initial-b-inspection-accepted",
    )
    functional = _act(functional, "finish-failed-functional-clearance", "continue_operation")
    wg03 = next(item for item in functional.backlog if item.generation_rule_id == "WG-03")
    functional = _act(
        functional,
        "failed-functional-start",
        "request_functional_check",
        pump_id="pump-b",
        backlog_item_id=wg03.item_id,
    )
    functional_transition = apply_process_outcome(
        functional,
        PumpStationProcessOutcomeRequest(
            request_id="fail-b-functional",
            authority_id="maintenance-controller",
            process_id=functional.processes[-1].process_id,
            outcome="failed",
            evidence_id="evidence-b-functional-failed-001",
            base_state_id=functional.state_id,
        ),
    )
    functional = functional_transition.state
    retained = functional.backlog_item(wg03.item_id)
    assert functional_transition.receipt.required_authorities == ("maintenance",)
    assert retained.status is PumpStationBacklogStatus.PLANNED
    assert retained.closure_evidence_ids == ("evidence-b-functional-failed-001",)
    assert len([item for item in functional.backlog if item.generation_rule_id == "WG-03"]) == 1

    verification = create_asw_8_world_state()
    verification = _act(
        verification,
        "failed-verification-start",
        "request_post_maintenance_verification",
        pump_id="pump-a",
        backlog_item_id="backlog-a-verification-001",
    )
    verification = apply_process_outcome(
        verification,
        PumpStationProcessOutcomeRequest(
            request_id="fail-a-verification",
            authority_id="verification-engineer-01",
            process_id=verification.processes[-1].process_id,
            outcome="failed",
            evidence_id="evidence-a-verification-failed-001",
            base_state_id=verification.state_id,
        ),
    ).state
    assert "restriction-a-run-in-001" in verification.active_restriction_ids
    assert len([item for item in verification.backlog if item.generation_rule_id == "WG-05"]) == 1


def test_common_hard_stop_requires_a_fresh_assignment_after_restore() -> None:
    state = create_asw_8_world_state()
    stopped = _set_power_boundary(state, "power-stop", available=False)

    assert stopped.physical.service_running_pump_ids == ()
    assert stopped.assignment.active is False
    assert all(
        not stopped.physical.availability(pump.pump_id).assured_for_outage_planning for pump in stopped.physical.pumps
    )
    with pytest.raises(PumpStationCoupledWorldError, match="assignment"):
        _act(
            stopped,
            "assignment-during-stop",
            "request_duty_assignment",
            ordered_pump_ids=("pump-c",),
        )

    restored = _set_power_boundary(stopped, "power-restore", available=True)
    assert restored.physical.service_running_pump_ids == ()
    assert restored.assignment.active is False

    reassigned = _act(
        restored,
        "assignment-after-restore",
        "request_duty_assignment",
        ordered_pump_ids=("pump-c",),
    )
    assert reassigned.physical.service_running_pump_ids == ("pump-c",)


def test_continue_operation_stops_at_the_first_named_runtime_boundary() -> None:
    state = create_asw_8_world_state()
    state = replace(
        state,
        assignment=replace(state.assignment, ordered_pump_ids=("pump-a", "pump-c")),
        physical=replace(
            state.physical.with_boundary_mode(
                "pump-a",
                state.physical.boundary("pump-c").mode,
                "runtime-clock-test",
            ),
            calendar_seconds=64_800,
            service_running_pump_ids=("pump-a", "pump-c"),
        ),
        backlog=(
            _runtime_backlog("pump-a-runtime-boundary", "pump-a", 5_400),
            _runtime_backlog("pump-c-runtime-boundary", "pump-c", 3_600),
        ),
    )

    advanced = _act(state, "continue-to-first-runtime-boundary", "continue_operation")

    assert advanced.calendar_seconds == 66_600
    assert advanced.physical.pump("pump-a").exposure.runtime_seconds == 5_400
    assert advanced.physical.pump("pump-c").exposure.runtime_seconds == 1_800
    assert advanced.event_effect_ids[-1] == "backlog-runtime-boundary-pump-a-runtime-boundary-due"


def test_assignment_rejects_avoidable_deficit_and_records_unavoidable_deficit() -> None:
    state = create_asw_8_world_state()
    peak = replace(
        state,
        physical=replace(state.physical, calendar_seconds=64_800),
    )
    unavoidable = _act(
        peak,
        "unavoidable-single-pump-peak",
        "request_duty_assignment",
        ordered_pump_ids=("pump-c",),
    )
    view = project_coupled_actor_view(unavoidable)

    assert unavoidable.assignment.required_service_scu == 2
    assert unavoidable.assignment.assigned_service_scu == 1
    assert unavoidable.assignment.unserved_service_scu == 1
    assert unavoidable.assignment.decision_detail == "accepted unavoidable degraded operation"
    assert view.required_service_scu == 2
    assert view.available_assured_scu == 1
    assert view.assigned_operating_scu == 1
    assert view.served_scu == 1
    assert view.unserved_scu == 1
    assert view.surplus_scu == 0

    avoidable_peak = replace(
        peak,
        physical=peak.physical.with_boundary_mode(
            "pump-a",
            peak.physical.boundary("pump-c").mode,
            "accepted-a-assurance",
        ),
    )
    with pytest.raises(PumpStationCoupledWorldError, match="avoidable-service-deficit"):
        _act(
            avoidable_peak,
            "avoidable-single-pump-peak",
            "request_duty_assignment",
            ordered_pump_ids=("pump-c",),
        )
