# ABOUTME: Implements ASW-8 resource pools, durable backlog, priority, and exact work generation.
# ABOUTME: Keeps task-owned work semantics separate from shared library contracts and persistence records.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import NoReturn, Self

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledPhysicalState,
    PumpStationServiceRequirement,
)


class PumpStationResourceError(ValueError):
    """Raised when resource quantities, windows, or reservations are invalid."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


class PumpStationWorkGenerationError(ValueError):
    """Raised when one stable generation key is used with different content."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _resource_fail(code: str, detail: str) -> NoReturn:
    raise PumpStationResourceError(code, detail)


class PumpStationResourceClass(StrEnum):
    """Closed resource-pool classes."""

    REUSABLE = "reusable"
    CONSUMABLE = "consumable"


class PumpStationPoolReservationStatus(StrEnum):
    """Closed lifecycle for one pool reservation."""

    RESERVED = "reserved"
    ACTIVE = "active"
    SUSPENDED_RETAINED = "suspended_retained"
    RELEASED = "released"
    CONSUMED = "consumed"
    CANCELLED = "cancelled"


class PumpStationCoupledProcessStatus(StrEnum):
    """Closed execution lifecycle for one ASW-8 process."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class PumpStationCoupledProcess:
    """One timed work process linked to durable recognised demand."""

    process_id: str
    kind: str
    target_id: str
    backlog_item_id: str
    started_at_calendar_seconds: int
    due_at_calendar_seconds: int
    remaining_duration_seconds: int
    required_pool_ids: tuple[str, ...]
    status: PumpStationCoupledProcessStatus


@dataclass(frozen=True, slots=True)
class PumpStationAvailabilityInterval:
    """One exact half-open reusable-resource window."""

    start_calendar_seconds: int
    end_calendar_seconds: int

    def covers(self, start: int, end: int) -> bool:
        """Return whether the full requested interval is available."""
        return self.start_calendar_seconds <= start and end <= self.end_calendar_seconds


@dataclass(frozen=True, slots=True)
class PumpStationReusablePool:
    """Quantity account for reusable temporal capacity."""

    pool_id: str
    capacity: int
    free: int
    reserved: int
    unavailable: int
    availability_intervals: tuple[PumpStationAvailabilityInterval, ...]
    resource_class: PumpStationResourceClass = PumpStationResourceClass.REUSABLE

    def __post_init__(self) -> None:
        if min(self.capacity, self.free, self.reserved, self.unavailable) < 0:
            _resource_fail("resource-quantity", self.pool_id)
        if self.capacity != self.free + self.reserved + self.unavailable:
            _resource_fail("resource-conservation", self.pool_id)


@dataclass(frozen=True, slots=True)
class PumpStationConsumablePool:
    """Quantity account for consumable stock."""

    pool_id: str
    on_hand: int
    free: int
    reserved: int
    arrivals: int = 0
    consumed: int = 0
    discarded: int = 0
    opening_on_hand: int = 1
    resource_class: PumpStationResourceClass = PumpStationResourceClass.CONSUMABLE

    def __post_init__(self) -> None:
        if (
            min(
                self.on_hand,
                self.free,
                self.reserved,
                self.arrivals,
                self.consumed,
                self.discarded,
                self.opening_on_hand,
            )
            < 0
        ):
            _resource_fail("resource-quantity", self.pool_id)
        if self.on_hand != self.free + self.reserved:
            _resource_fail("resource-conservation", self.pool_id)
        if self.opening_on_hand + self.arrivals != self.on_hand + self.consumed + self.discarded:
            _resource_fail("resource-conservation", self.pool_id)


PumpStationResourcePool = PumpStationReusablePool | PumpStationConsumablePool


@dataclass(frozen=True, slots=True)
class PumpStationResourceState:
    """Complete current resource-pool state."""

    pools: tuple[PumpStationResourcePool, ...]

    def __post_init__(self) -> None:
        if len({pool.pool_id for pool in self.pools}) != len(self.pools):
            _resource_fail("resource-inventory", "pool identities must be distinct")

    def pool(self, pool_id: str) -> PumpStationResourcePool:
        """Return one pool by stable identity."""
        for pool in self.pools:
            if pool.pool_id == pool_id:
                return pool
        _resource_fail("unknown-resource-pool", pool_id)

    def with_pool(self, updated: PumpStationResourcePool) -> Self:
        """Return state with one matching pool replaced."""
        self.pool(updated.pool_id)
        return replace(
            self,
            pools=tuple(updated if pool.pool_id == updated.pool_id else pool for pool in self.pools),
        )


@dataclass(frozen=True, slots=True)
class PumpStationPoolReservation:
    """Quantity-bearing reservation for one process and one pool."""

    reservation_id: str
    pool_id: str
    quantity: int
    process_id: str
    target_id: str
    status: PumpStationPoolReservationStatus
    created_at_calendar_seconds: int
    released_at_calendar_seconds: int | None
    retain_on_suspension: bool
    prior_reservation_id: str | None
    disposition: str | None


@dataclass(frozen=True, slots=True)
class PumpStationResourceConservation:
    """Derived validity result for all current pool accounts."""

    valid: bool
    failure_pool_ids: tuple[str, ...]


def create_asw_8_resource_state() -> PumpStationResourceState:
    """Return the exact opening pool quantities and work windows."""
    windows = (
        PumpStationAvailabilityInterval(21_600, 61_200),
        PumpStationAvailabilityInterval(108_000, 165_600),
        PumpStationAvailabilityInterval(194_400, 226_800),
    )
    reusable = tuple(
        PumpStationReusablePool(
            pool_id=pool_id,
            capacity=1,
            free=1,
            reserved=0,
            unavailable=0,
            availability_intervals=windows,
        )
        for pool_id in (
            "field-access-slot",
            "lifting-isolation-set-01",
            "diagnostic-test-set-01",
            "maintenance-crew-01",
            "verification-engineer-01",
        )
    )
    return PumpStationResourceState(
        pools=(
            *reusable,
            PumpStationConsumablePool(
                pool_id="obstruction-clearance-kit",
                on_hand=1,
                free=1,
                reserved=0,
            ),
        )
    )


def _reservation_ordinal(
    reservations: tuple[PumpStationPoolReservation, ...],
    pool_id: str,
    process_id: str,
) -> int:
    return 1 + sum(
        reservation.pool_id == pool_id and reservation.process_id == process_id for reservation in reservations
    )


def reserve_process_resources(
    resources: PumpStationResourceState,
    reservations: tuple[PumpStationPoolReservation, ...],
    *,
    process_id: str,
    target_id: str,
    pool_ids: tuple[str, ...],
    now_calendar_seconds: int,
    duration_seconds: int,
) -> tuple[PumpStationResourceState, tuple[PumpStationPoolReservation, ...]]:
    """Atomically reserve one unit from each required pool for the full duration."""
    if len(set(pool_ids)) != len(pool_ids) or duration_seconds <= 0:
        _resource_fail("resource-request", "pool identities or duration are invalid")
    selected = tuple(resources.pool(pool_id) for pool_id in pool_ids)
    for pool in selected:
        if pool.free < 1:
            _resource_fail("resource-unavailable", pool.pool_id)
        if isinstance(pool, PumpStationReusablePool) and not any(
            window.covers(now_calendar_seconds, now_calendar_seconds + duration_seconds)
            for window in pool.availability_intervals
        ):
            _resource_fail("resource-window", pool.pool_id)
    updated_resources = resources
    updated_reservations = list(reservations)
    for pool in selected:
        if isinstance(pool, PumpStationReusablePool):
            updated_pool: PumpStationResourcePool = replace(
                pool,
                free=pool.free - 1,
                reserved=pool.reserved + 1,
            )
            retained = False
        else:
            updated_pool = replace(pool, free=pool.free - 1, reserved=pool.reserved + 1)
            retained = True
        updated_resources = updated_resources.with_pool(updated_pool)
        ordinal = _reservation_ordinal(reservations, pool.pool_id, process_id)
        updated_reservations.append(
            PumpStationPoolReservation(
                reservation_id=f"reservation-{process_id}-{pool.pool_id}-{ordinal}",
                pool_id=pool.pool_id,
                quantity=1,
                process_id=process_id,
                target_id=target_id,
                status=PumpStationPoolReservationStatus.ACTIVE,
                created_at_calendar_seconds=now_calendar_seconds,
                released_at_calendar_seconds=None,
                retain_on_suspension=retained,
                prior_reservation_id=None,
                disposition=None,
            )
        )
    result = tuple(updated_reservations)
    if not resource_conservation(updated_resources, result).valid:
        _resource_fail("resource-conservation", "reservation account differs")
    return updated_resources, result


def retain_consumable_reservations(
    resources: PumpStationResourceState,
    reservations: tuple[PumpStationPoolReservation, ...],
    *,
    now_calendar_seconds: int,
) -> tuple[PumpStationResourceState, tuple[PumpStationPoolReservation, ...]]:
    """Release reusable reservations and retain consumable stock on suspension."""
    updated_resources = resources
    updated: list[PumpStationPoolReservation] = []
    for reservation in reservations:
        if reservation.status is not PumpStationPoolReservationStatus.ACTIVE:
            updated.append(reservation)
            continue
        pool = updated_resources.pool(reservation.pool_id)
        if reservation.retain_on_suspension:
            updated.append(replace(reservation, status=PumpStationPoolReservationStatus.SUSPENDED_RETAINED))
            continue
        if not isinstance(pool, PumpStationReusablePool):
            _resource_fail("resource-class", reservation.pool_id)
        updated_resources = updated_resources.with_pool(replace(pool, free=pool.free + 1, reserved=pool.reserved - 1))
        updated.append(
            replace(
                reservation,
                status=PumpStationPoolReservationStatus.RELEASED,
                released_at_calendar_seconds=now_calendar_seconds,
                disposition="released_on_suspension",
            )
        )
    result = tuple(updated)
    if not resource_conservation(updated_resources, result).valid:
        _resource_fail("resource-conservation", "suspension account differs")
    return updated_resources, result


def resume_process_reservations(
    resources: PumpStationResourceState,
    reservations: tuple[PumpStationPoolReservation, ...],
    *,
    process_id: str,
    target_id: str,
    required_pool_ids: tuple[str, ...],
    now_calendar_seconds: int,
    remaining_duration_seconds: int,
) -> tuple[PumpStationResourceState, tuple[PumpStationPoolReservation, ...]]:
    """Reactivate retained stock and reserve fresh reusable capacity on resume."""
    retained_pool_ids = {
        item.pool_id
        for item in reservations
        if item.process_id == process_id and item.status is PumpStationPoolReservationStatus.SUSPENDED_RETAINED
    }
    missing_pool_ids = tuple(pool_id for pool_id in required_pool_ids if pool_id not in retained_pool_ids)
    updated_resources, updated_reservations = reserve_process_resources(
        resources,
        reservations,
        process_id=process_id,
        target_id=target_id,
        pool_ids=missing_pool_ids,
        now_calendar_seconds=now_calendar_seconds,
        duration_seconds=remaining_duration_seconds,
    )
    updated_reservations = tuple(
        replace(item, status=PumpStationPoolReservationStatus.ACTIVE)
        if item.process_id == process_id and item.status is PumpStationPoolReservationStatus.SUSPENDED_RETAINED
        else item
        for item in updated_reservations
    )
    if not resource_conservation(updated_resources, updated_reservations).valid:
        _resource_fail("resource-conservation", "resume account differs")
    return updated_resources, updated_reservations


def cancel_process_reservations(
    resources: PumpStationResourceState,
    reservations: tuple[PumpStationPoolReservation, ...],
    *,
    process_id: str,
    now_calendar_seconds: int,
) -> tuple[PumpStationResourceState, tuple[PumpStationPoolReservation, ...]]:
    """Cancel retained stock and any active reservations without consuming them."""
    updated_resources = resources
    updated: list[PumpStationPoolReservation] = []
    for reservation in reservations:
        if reservation.process_id != process_id or reservation.status not in {
            PumpStationPoolReservationStatus.ACTIVE,
            PumpStationPoolReservationStatus.SUSPENDED_RETAINED,
        }:
            updated.append(reservation)
            continue
        pool = updated_resources.pool(reservation.pool_id)
        updated_resources = updated_resources.with_pool(
            replace(
                pool,
                free=pool.free + reservation.quantity,
                reserved=pool.reserved - reservation.quantity,
            )
        )
        updated.append(
            replace(
                reservation,
                status=PumpStationPoolReservationStatus.CANCELLED,
                released_at_calendar_seconds=now_calendar_seconds,
                disposition="cancelled_unused",
            )
        )
    result = tuple(updated)
    if not resource_conservation(updated_resources, result).valid:
        _resource_fail("resource-conservation", "cancellation account differs")
    return updated_resources, result


def consume_reservation(
    resources: PumpStationResourceState,
    reservations: tuple[PumpStationPoolReservation, ...],
    *,
    pool_id: str,
    process_id: str,
    now_calendar_seconds: int,
) -> tuple[PumpStationResourceState, tuple[PumpStationPoolReservation, ...]]:
    """Consume one retained or active consumable reservation after successful work."""
    pool = resources.pool(pool_id)
    if not isinstance(pool, PumpStationConsumablePool):
        _resource_fail("resource-class", pool_id)
    matches = [
        item
        for item in reservations
        if item.pool_id == pool_id
        and item.process_id == process_id
        and item.status
        in {PumpStationPoolReservationStatus.ACTIVE, PumpStationPoolReservationStatus.SUSPENDED_RETAINED}
    ]
    if len(matches) != 1:
        _resource_fail("reservation-state", pool_id)
    selected = matches[0]
    updated_pool = replace(
        pool,
        on_hand=pool.on_hand - selected.quantity,
        reserved=pool.reserved - selected.quantity,
        consumed=pool.consumed + selected.quantity,
    )
    updated = tuple(
        replace(
            item,
            status=PumpStationPoolReservationStatus.CONSUMED,
            released_at_calendar_seconds=now_calendar_seconds,
            disposition="consumed_on_success",
        )
        if item.reservation_id == selected.reservation_id
        else item
        for item in reservations
    )
    return resources.with_pool(updated_pool), updated


def release_reservations(
    resources: PumpStationResourceState,
    reservations: tuple[PumpStationPoolReservation, ...],
    *,
    process_id: str,
    now_calendar_seconds: int,
) -> tuple[PumpStationResourceState, tuple[PumpStationPoolReservation, ...]]:
    """Release all still-active reusable reservations after process completion."""
    updated_resources = resources
    updated: list[PumpStationPoolReservation] = []
    for reservation in reservations:
        if reservation.process_id != process_id or reservation.status is not PumpStationPoolReservationStatus.ACTIVE:
            updated.append(reservation)
            continue
        pool = updated_resources.pool(reservation.pool_id)
        if isinstance(pool, PumpStationConsumablePool):
            _resource_fail("reservation-state", f"unused consumable {pool.pool_id} needs an explicit disposition")
        updated_resources = updated_resources.with_pool(
            replace(pool, free=pool.free + reservation.quantity, reserved=pool.reserved - reservation.quantity)
        )
        updated.append(
            replace(
                reservation,
                status=PumpStationPoolReservationStatus.RELEASED,
                released_at_calendar_seconds=now_calendar_seconds,
                disposition="released_on_completion",
            )
        )
    result = tuple(updated)
    if not resource_conservation(updated_resources, result).valid:
        _resource_fail("resource-conservation", "completion account differs")
    return updated_resources, result


def resource_conservation(
    resources: PumpStationResourceState,
    reservations: tuple[PumpStationPoolReservation, ...],
) -> PumpStationResourceConservation:
    """Independently compare pool quantities with all live reservations."""
    failures: list[str] = []
    live_statuses = {
        PumpStationPoolReservationStatus.RESERVED,
        PumpStationPoolReservationStatus.ACTIVE,
        PumpStationPoolReservationStatus.SUSPENDED_RETAINED,
    }
    for pool in resources.pools:
        live_quantity = sum(
            item.quantity for item in reservations if item.pool_id == pool.pool_id and item.status in live_statuses
        )
        if pool.reserved != live_quantity:
            failures.append(pool.pool_id)
        if isinstance(pool, PumpStationReusablePool):
            if pool.capacity != pool.free + pool.reserved + pool.unavailable:
                failures.append(pool.pool_id)
        elif (
            pool.on_hand != pool.free + pool.reserved
            or pool.opening_on_hand + pool.arrivals != pool.on_hand + pool.consumed + pool.discarded
        ):
            failures.append(pool.pool_id)
    return PumpStationResourceConservation(
        valid=not failures,
        failure_pool_ids=tuple(sorted(set(failures))),
    )


class PumpStationPriority(StrEnum):
    """Closed urgency levels ordered from most to least urgent."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class PumpStationBacklogStatus(StrEnum):
    """Closed durable work-demand lifecycle."""

    OPEN = "open"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CLOSED = "closed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class PumpStationBacklogItem:
    """One durable recognised demand for work."""

    item_id: str
    work_type: str
    target_kind: str
    target_id: str
    generation_rule_id: str
    generation_ordinal: int
    originating_record_id: str
    linked_obligation_ids: tuple[str, ...]
    linked_restriction_ids: tuple[str, ...]
    linked_work_order_id: str | None
    linked_process_id: str | None
    generated_at_calendar_seconds: int
    base_priority: PumpStationPriority
    effective_priority: PumpStationPriority
    due_calendar_seconds: int | None
    due_runtime_clock_kind: str | None
    due_runtime_clock_id: str | None
    due_runtime_limit_seconds: int | None
    status: PumpStationBacklogStatus
    blocked_from_status: PumpStationBacklogStatus | None
    blocked_since_calendar_seconds: int | None
    accumulated_blocked_seconds: int
    closure_rule: str
    closure_evidence_ids: tuple[str, ...]
    supersedes_item_id: str | None
    superseded_by_item_id: str | None

    @property
    def semantic_key(self) -> tuple[str, str, str, int]:
        """Return the transport-neutral generated-work identity."""
        return (
            self.generation_rule_id,
            self.target_kind,
            self.target_id,
            self.generation_ordinal,
        )


@dataclass(frozen=True, slots=True)
class PumpStationWorkGenerationRecord:
    """Stable exactly-once source identity for one generated backlog item."""

    rule_id: str
    source_transition_id: str
    target_kind: str
    target_id: str
    generation_ordinal: int
    backlog_item_id: str

    @property
    def key(self) -> tuple[str, str, str, str, int]:
        """Return the exact generation key."""
        return (
            self.rule_id,
            self.source_transition_id,
            self.target_kind,
            self.target_id,
            self.generation_ordinal,
        )


def generate_work_once(
    records: tuple[PumpStationWorkGenerationRecord, ...],
    backlog: tuple[PumpStationBacklogItem, ...],
    generation: PumpStationWorkGenerationRecord,
    item: PumpStationBacklogItem,
) -> tuple[tuple[PumpStationWorkGenerationRecord, ...], tuple[PumpStationBacklogItem, ...]]:
    """Create one stable item or return the exact existing content on retry."""
    if generation.backlog_item_id != item.item_id:
        raise PumpStationWorkGenerationError("generation-link", item.item_id)
    existing = tuple(record for record in records if record.key == generation.key)
    if existing:
        if existing != (generation,):
            raise PumpStationWorkGenerationError("generation-content-mismatch", item.item_id)
        linked = tuple(value for value in backlog if value.item_id == generation.backlog_item_id)
        if linked != (item,):
            raise PumpStationWorkGenerationError("generation-content-mismatch", item.item_id)
        return records, backlog
    if any(value.item_id == item.item_id for value in backlog):
        raise PumpStationWorkGenerationError("generation-content-mismatch", item.item_id)
    return (*records, generation), (*backlog, item)


def planned_outage_admissible(
    state: PumpStationCoupledPhysicalState,
    *,
    target_pump_id: str,
    start_calendar_seconds: int,
    completion_calendar_seconds: int,
    visible_service_schedule: tuple[PumpStationServiceRequirement, ...],
    disclosed_through_calendar_seconds: int,
) -> bool:
    """Return whether assured non-target capacity covers each disclosed work interval."""
    if completion_calendar_seconds > disclosed_through_calendar_seconds:
        return False
    if target_pump_id in state.service_running_pump_ids or target_pump_id in state.test_running_pump_ids:
        return False
    assured_non_target = sum(
        state.availability(pump.pump_id).assured_for_outage_planning
        for pump in state.pumps
        if pump.pump_id != target_pump_id
    )
    relevant = tuple(
        requirement
        for requirement in visible_service_schedule
        if requirement.start_calendar_seconds < completion_calendar_seconds
        and requirement.end_calendar_seconds > start_calendar_seconds
    )
    if not relevant:
        return False
    cursor = start_calendar_seconds
    for requirement in sorted(relevant, key=lambda item: item.start_calendar_seconds):
        if requirement.start_calendar_seconds > cursor or requirement.required_service_scu > assured_non_target:
            return False
        cursor = max(cursor, min(requirement.end_calendar_seconds, completion_calendar_seconds))
    return cursor >= completion_calendar_seconds


_PRIORITY_ORDER = {
    PumpStationPriority.P0: 0,
    PumpStationPriority.P1: 1,
    PumpStationPriority.P2: 2,
    PumpStationPriority.P3: 3,
}
D_CALENDAR_SECONDS = 28_800
D_RUNTIME_SECONDS = 28_800


def effective_priority(
    item: PumpStationBacklogItem,
    *,
    now_calendar_seconds: int,
    runtime_clock_seconds: int | None = None,
) -> PumpStationPriority:
    """Apply exact inclusive calendar, runtime, and blocked-age urgency rules."""
    candidates = [item.base_priority]
    if item.due_calendar_seconds is not None:
        slack = item.due_calendar_seconds - now_calendar_seconds
        candidates.append(
            PumpStationPriority.P1
            if slack <= D_CALENDAR_SECONDS
            else PumpStationPriority.P2
            if slack <= 2 * D_CALENDAR_SECONDS
            else PumpStationPriority.P3
        )
    if item.due_runtime_limit_seconds is not None and runtime_clock_seconds is not None:
        slack = item.due_runtime_limit_seconds - runtime_clock_seconds
        candidates.append(
            PumpStationPriority.P1
            if slack <= D_RUNTIME_SECONDS
            else PumpStationPriority.P2
            if slack <= 2 * D_RUNTIME_SECONDS
            else PumpStationPriority.P3
        )
    blocked_age = item.accumulated_blocked_seconds
    if item.blocked_since_calendar_seconds is not None:
        blocked_age += now_calendar_seconds - item.blocked_since_calendar_seconds
    if item.due_calendar_seconds is None and item.due_runtime_limit_seconds is None:
        if blocked_age >= 4 * D_CALENDAR_SECONDS:
            candidates.append(PumpStationPriority.P1)
        elif blocked_age >= 2 * D_CALENDAR_SECONDS:
            candidates.append(PumpStationPriority.P2)
    return min(candidates, key=_PRIORITY_ORDER.__getitem__)


def sort_eligible_backlog(
    backlog: tuple[PumpStationBacklogItem, ...],
    *,
    now_calendar_seconds: int,
    runtime_clock_values: Mapping[tuple[str, str], int] | None = None,
) -> tuple[PumpStationBacklogItem, ...]:
    """Return the fixed priority, due, slack, age, and identity order."""
    eligible_statuses = {PumpStationBacklogStatus.OPEN, PumpStationBacklogStatus.PLANNED}
    clocks = runtime_clock_values or {}
    refreshed: list[tuple[PumpStationBacklogItem, int | None]] = []
    for item in backlog:
        if item.status not in eligible_statuses:
            continue
        runtime_clock = (
            clocks.get((item.due_runtime_clock_kind, item.due_runtime_clock_id))
            if item.due_runtime_clock_kind is not None and item.due_runtime_clock_id is not None
            else None
        )
        runtime_slack = (
            item.due_runtime_limit_seconds - runtime_clock
            if item.due_runtime_limit_seconds is not None and runtime_clock is not None
            else None
        )
        refreshed.append(
            (
                replace(
                    item,
                    effective_priority=effective_priority(
                        item,
                        now_calendar_seconds=now_calendar_seconds,
                        runtime_clock_seconds=runtime_clock,
                    ),
                ),
                runtime_slack,
            )
        )
    far_future = 2**62
    return tuple(
        item
        for item, _runtime_slack in sorted(
            refreshed,
            key=lambda row: (
                _PRIORITY_ORDER[row[0].effective_priority],
                0
                if (row[0].due_calendar_seconds is not None and row[0].due_calendar_seconds <= now_calendar_seconds)
                or (row[1] is not None and row[1] <= 0)
                else 1,
                row[0].due_calendar_seconds - now_calendar_seconds
                if row[0].due_calendar_seconds is not None
                else far_future,
                row[1] if row[1] is not None else far_future,
                -(now_calendar_seconds - row[0].generated_at_calendar_seconds),
                row[0].item_id,
            ),
        )
    )
