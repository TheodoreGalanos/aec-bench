# ABOUTME: Runs the complete ASW-8 Day 0 to Day 2 reference journey through closed actions.
# ABOUTME: Checks explicit Operations reviews, exact work generation, and the declared terminal state.

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PUMP_STATION_OPERATIONS_REVIEW_VERSION,
    PumpStationCoupledWorldError,
    PumpStationCoupledWorldState,
    PumpStationOperationsBoundaryReviewRequest,
    apply_coupled_actor_action,
    apply_operations_boundary_review,
    create_asw_8_world_state,
    project_coupled_actor_view,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogStatus,
    PumpStationConsumablePool,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationPumpMode,
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
            version=PUMP_STATION_OPERATIONS_REVIEW_VERSION,
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


def test_projection_v5_presents_dates_and_complete_planning_windows() -> None:
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
        version=PUMP_STATION_OPERATIONS_REVIEW_VERSION,
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
