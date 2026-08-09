# ABOUTME: Tests ASW-8 resource pools, outage admission, work generation, and priority.
# ABOUTME: Covers shared-lane exclusion and independent resource, work, and liability balances.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from typing import Any, cast

import pytest

from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogItem,
    PumpStationBacklogStatus,
    PumpStationConsumablePool,
    PumpStationPoolReservationStatus,
    PumpStationPriority,
    PumpStationResourceError,
    PumpStationResourceState,
    PumpStationWorkGenerationError,
    PumpStationWorkGenerationRecord,
    consume_reservation,
    create_resource_state,
    effective_priority,
    generate_work_once,
    planned_outage_admissible,
    release_reservations,
    reserve_process_resources,
    resource_conservation,
    retain_consumable_reservations,
    sort_eligible_backlog,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.physical_models import (
    PumpState,
    PumpStationPumpMode,
    PumpStationServiceRequirement,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    create_opening_physical_state,
    load_reference_system,
)


def _opening_resource_state() -> PumpStationResourceState:
    specification = cast(Mapping[str, Any], load_reference_system().opening_state["resource_state"])
    return create_resource_state(specification)


def _backlog(
    *,
    item_id: str,
    rule: str,
    target: str,
    generated: int,
    due: int | None,
    priority: PumpStationPriority,
) -> PumpStationBacklogItem:
    return PumpStationBacklogItem(
        item_id=item_id,
        work_type="inspection",
        target_kind="asset",
        target_id=target,
        generation_rule_id=rule,
        generation_ordinal=1,
        originating_record_id=f"source-{item_id}",
        linked_obligation_ids=(),
        linked_restriction_ids=(),
        linked_work_order_id=None,
        linked_process_id=None,
        generated_at_calendar_seconds=generated,
        base_priority=priority,
        effective_priority=priority,
        due_calendar_seconds=due,
        due_runtime_clock_kind=None,
        due_runtime_clock_id=None,
        due_runtime_limit_seconds=None,
        status=PumpStationBacklogStatus.PLANNED,
        blocked_from_status=None,
        blocked_since_calendar_seconds=None,
        accumulated_blocked_seconds=0,
        closure_rule="accepted inspection",
        closure_evidence_ids=(),
        supersedes_item_id=None,
        superseded_by_item_id=None,
    )


def test_shared_pool_cannot_be_overallocated_and_conserves_quantity() -> None:
    resources = _opening_resource_state()
    resources, reservations = reserve_process_resources(
        resources,
        (),
        process_id="process-b-clearance",
        target_id="pump-b",
        pool_ids=(
            "field-access-slot",
            "lifting-isolation-set-01",
            "maintenance-crew-01",
            "obstruction-clearance-kit",
        ),
        now_calendar_seconds=108_000,
        duration_seconds=14_400,
    )

    with pytest.raises(PumpStationResourceError) as raised:
        reserve_process_resources(
            resources,
            reservations,
            process_id="process-c-inspection",
            target_id="pump-c",
            pool_ids=("field-access-slot", "maintenance-crew-01"),
            now_calendar_seconds=108_000,
            duration_seconds=14_400,
        )

    assert raised.value.code == "resource-unavailable"
    assert resource_conservation(resources, reservations).valid

    with pytest.raises(PumpStationResourceError) as window_error:
        reserve_process_resources(
            _opening_resource_state(),
            (),
            process_id="process-too-long-for-window",
            target_id="pump-b",
            pool_ids=("field-access-slot",),
            now_calendar_seconds=60_000,
            duration_seconds=3_600,
        )
    assert window_error.value.code == "resource-window"


def test_suspension_retains_kit_but_releases_reusable_pools() -> None:
    resources, reservations = reserve_process_resources(
        _opening_resource_state(),
        (),
        process_id="process-b-clearance",
        target_id="pump-b",
        pool_ids=("field-access-slot", "maintenance-crew-01", "obstruction-clearance-kit"),
        now_calendar_seconds=108_000,
        duration_seconds=14_400,
    )

    suspended_resources, suspended = retain_consumable_reservations(
        resources,
        reservations,
        now_calendar_seconds=110_000,
    )

    kit = suspended_resources.pool("obstruction-clearance-kit")
    access = suspended_resources.pool("field-access-slot")
    assert kit.reserved == 1
    assert access.free == 1
    assert {item.status for item in suspended} == {
        PumpStationPoolReservationStatus.RELEASED,
        PumpStationPoolReservationStatus.SUSPENDED_RETAINED,
    }
    assert resource_conservation(suspended_resources, suspended).valid

    consumed_resources, consumed = consume_reservation(
        suspended_resources,
        suspended,
        pool_id="obstruction-clearance-kit",
        process_id="process-b-clearance",
        now_calendar_seconds=122_400,
    )
    final_resources, final_reservations = release_reservations(
        consumed_resources,
        consumed,
        process_id="process-b-clearance",
        now_calendar_seconds=122_400,
    )
    final_kit = final_resources.pool("obstruction-clearance-kit")
    assert isinstance(final_kit, PumpStationConsumablePool)
    assert final_kit.on_hand == 0
    assert resource_conservation(final_resources, final_reservations).valid


def test_generation_is_exactly_once_and_changed_content_fails() -> None:
    generation = PumpStationWorkGenerationRecord(
        rule_id="WG-07",
        source_transition_id="close-peak",
        target_kind="asset",
        target_id="pump-c",
        generation_ordinal=1,
        backlog_item_id="generated",
    )
    item = _backlog(
        item_id="generated",
        rule="WG-07",
        target="pump-c",
        generated=93_600,
        due=151_200,
        priority=PumpStationPriority.P2,
    )

    first = generate_work_once((), (), generation, item)
    retried = generate_work_once(first[0], first[1], generation, item)

    assert retried == first
    with pytest.raises(PumpStationWorkGenerationError) as raised:
        generate_work_once(
            first[0],
            first[1],
            generation,
            replace(item, due_calendar_seconds=151_201),
        )
    assert raised.value.code == "generation-content-mismatch"


def test_collateral_item_crosses_inclusive_priority_boundary_and_ranks_first() -> None:
    collateral = _backlog(
        item_id="c-inspection",
        rule="WG-07",
        target="pump-c",
        generated=93_600,
        due=151_200,
        priority=PumpStationPriority.P2,
    )
    b_verification = _backlog(
        item_id="b-verification",
        rule="WG-04",
        target="pump-b",
        generated=126_000,
        due=183_600,
        priority=PumpStationPriority.P1,
    )

    assert effective_priority(collateral, now_calendar_seconds=108_000) is PumpStationPriority.P2
    assert effective_priority(collateral, now_calendar_seconds=122_400) is PumpStationPriority.P1
    ranked = sort_eligible_backlog((b_verification, collateral), now_calendar_seconds=126_000)
    assert tuple(item.item_id for item in ranked) == ("c-inspection", "b-verification")


def test_runtime_priority_uses_current_named_clock_and_due_state() -> None:
    runtime_due = replace(
        _backlog(
            item_id="runtime-due",
            rule="WG-04",
            target="pump-a",
            generated=64_800,
            due=None,
            priority=PumpStationPriority.P3,
        ),
        due_runtime_clock_kind="pump_total",
        due_runtime_clock_id="pump-a",
        due_runtime_limit_seconds=5_400,
    )
    calendar_close = _backlog(
        item_id="calendar-close",
        rule="WG-01",
        target="pump-c",
        generated=64_800,
        due=65_000,
        priority=PumpStationPriority.P3,
    )

    ranked = sort_eligible_backlog(
        (calendar_close, runtime_due),
        now_calendar_seconds=64_800,
        runtime_clock_values={("pump_total", "pump-a"): 5_400},
    )

    assert tuple(item.item_id for item in ranked) == ("runtime-due", "calendar-close")
    assert ranked[0].effective_priority is PumpStationPriority.P1


def test_outage_admission_uses_only_visible_schedule_and_assured_capacity() -> None:
    state = create_opening_physical_state().with_boundary_mode(
        "pump-a",
        PumpStationPumpMode.SERVICE_AVAILABLE,
        "operations-review-a-001",
    )
    visible = (
        PumpStationServiceRequirement(21_600, 64_800, 1),
        PumpStationServiceRequirement(64_800, 93_600, 2),
    )

    assert not planned_outage_admissible(
        state,
        target_pump_id="pump-c",
        start_calendar_seconds=21_600,
        completion_calendar_seconds=64_900,
        visible_service_schedule=visible,
        disclosed_through_calendar_seconds=93_600,
    )
    normal_only = (PumpStationServiceRequirement(194_400, 226_800, 1),)
    day_two_state = replace(
        state,
        calendar_seconds=194_400,
        service_running_pump_ids=("pump-a",),
    )
    assert planned_outage_admissible(
        day_two_state,
        target_pump_id="pump-c",
        start_calendar_seconds=194_400,
        completion_calendar_seconds=223_200,
        visible_service_schedule=normal_only,
        disclosed_through_calendar_seconds=226_800,
    )


def test_outage_admission_is_equal_for_actor_equivalent_latent_states() -> None:
    visible_state = create_opening_physical_state().with_boundary_mode(
        "pump-a",
        PumpStationPumpMode.SERVICE_AVAILABLE,
        "operations-review-a-001",
    )
    latent_variant = replace(
        visible_state,
        pumps=cast(
            tuple[PumpState, PumpState, PumpState],
            tuple(
                replace(
                    pump,
                    condition=replace(
                        pump.condition,
                        obstruction=Decimal("0.99"),
                    ),
                )
                if pump.pump_id == "pump-c"
                else pump
                for pump in visible_state.pumps
            ),
        ),
    )
    visible = (PumpStationServiceRequirement(21_600, 64_800, 1),)

    decisions = tuple(
        planned_outage_admissible(
            state,
            target_pump_id="pump-b",
            start_calendar_seconds=21_600,
            completion_calendar_seconds=36_000,
            visible_service_schedule=visible,
            disclosed_through_calendar_seconds=64_800,
        )
        for state in (visible_state, latent_variant)
    )

    assert decisions == (True, True)
