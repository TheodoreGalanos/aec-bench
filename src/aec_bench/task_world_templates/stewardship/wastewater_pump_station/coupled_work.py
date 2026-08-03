# ABOUTME: Implements ASW-8 resource pools, durable backlog, priority, and exact work generation.
# ABOUTME: Keeps task-owned work semantics separate from shared library contracts and persistence records.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import NoReturn, Self


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


def record_consumable_arrival(
    resources: PumpStationResourceState,
    *,
    pool_id: str,
    quantity: int,
) -> PumpStationResourceState:
    """Record one declared stock arrival without changing reserved stock."""
    if quantity <= 0:
        _resource_fail("resource-quantity", pool_id)
    pool = resources.pool(pool_id)
    if not isinstance(pool, PumpStationConsumablePool):
        _resource_fail("resource-class", pool_id)
    return resources.with_pool(
        replace(
            pool,
            on_hand=pool.on_hand + quantity,
            free=pool.free + quantity,
            arrivals=pool.arrivals + quantity,
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


@dataclass(frozen=True, slots=True)
class PumpStationWorkGenerationResult:
    """Updated generation and backlog collections after one idempotent attempt."""

    records: tuple[PumpStationWorkGenerationRecord, ...]
    backlog: tuple[PumpStationBacklogItem, ...]


@dataclass(frozen=True, slots=True)
class PumpStationDeclaredWorkTrigger:
    """Typed source facts for one of the closed WG-01 to WG-09 rules."""

    rule_id: str
    source_transition_id: str
    target_kind: str
    target_id: str
    generation_ordinal: int
    generated_at_calendar_seconds: int
    current_runtime_seconds: int = 0
    next_capacity_critical_calendar_seconds: int | None = None
    linked_clearance_due_calendar_seconds: int | None = None
    linked_obligation_ids: tuple[str, ...] = ()
    linked_restriction_ids: tuple[str, ...] = ()
    existing_item_id: str | None = None
    target_is_serving: bool = False
    blocks_urgent_work: bool = False


def generate_work_once(
    records: tuple[PumpStationWorkGenerationRecord, ...],
    backlog: tuple[PumpStationBacklogItem, ...],
    generation: PumpStationWorkGenerationRecord,
    item: PumpStationBacklogItem,
) -> PumpStationWorkGenerationResult:
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
        return PumpStationWorkGenerationResult(records=records, backlog=backlog)
    if any(value.item_id == item.item_id for value in backlog):
        raise PumpStationWorkGenerationError("generation-content-mismatch", item.item_id)
    return PumpStationWorkGenerationResult(
        records=(*records, generation),
        backlog=(*backlog, item),
    )


def apply_declared_work_generation(
    records: tuple[PumpStationWorkGenerationRecord, ...],
    backlog: tuple[PumpStationBacklogItem, ...],
    trigger: PumpStationDeclaredWorkTrigger,
) -> PumpStationWorkGenerationResult:
    """Apply exactly one closed WG-01 to WG-09 generation or retention rule."""
    if trigger.rule_id in {"WG-08", "WG-09"}:
        if trigger.existing_item_id is None:
            raise PumpStationWorkGenerationError("generation-existing-item", trigger.rule_id)
        matching = tuple(item for item in backlog if item.item_id == trigger.existing_item_id)
        if len(matching) != 1:
            raise PumpStationWorkGenerationError("generation-existing-item", trigger.existing_item_id)
        item = matching[0]
        if trigger.rule_id == "WG-08":
            if item.status not in {
                PumpStationBacklogStatus.OPEN,
                PumpStationBacklogStatus.PLANNED,
                PumpStationBacklogStatus.IN_PROGRESS,
            }:
                raise PumpStationWorkGenerationError("generation-item-state", item.item_id)
            updated = replace(
                item,
                status=PumpStationBacklogStatus.BLOCKED,
                blocked_from_status=item.status,
                blocked_since_calendar_seconds=trigger.generated_at_calendar_seconds,
            )
        else:
            if item.status is not PumpStationBacklogStatus.BLOCKED:
                raise PumpStationWorkGenerationError("generation-item-state", item.item_id)
            updated = replace(
                item,
                status=PumpStationBacklogStatus.PLANNED,
                blocked_from_status=None,
                accumulated_blocked_seconds=(
                    item.accumulated_blocked_seconds
                    + trigger.generated_at_calendar_seconds
                    - (item.blocked_since_calendar_seconds or trigger.generated_at_calendar_seconds)
                ),
                blocked_since_calendar_seconds=None,
            )
        return PumpStationWorkGenerationResult(
            records=records,
            backlog=tuple(updated if value.item_id == item.item_id else value for value in backlog),
        )
    specifications = {
        "WG-01": ("inspection", "accepted inspection evidence", PumpStationPriority.P2),
        "WG-02": (
            "obstruction_clearance",
            "successful clearance and functional-check generation",
            PumpStationPriority.P2,
        ),
        "WG-03": ("minimum_functional_check", "accepted functional-check evidence", PumpStationPriority.P1),
        "WG-04": (
            "post_maintenance_verification",
            "accepted verification and Operations restriction review",
            PumpStationPriority.P1,
        ),
        "WG-05": ("rework_investigation", "accepted rework investigation", PumpStationPriority.P1),
        "WG-06": (
            "replenish_clearance_kit",
            "declared stock arrival is durably recorded",
            PumpStationPriority.P2,
        ),
        "WG-07": ("collateral_duty_inspection", "accepted target inspection", PumpStationPriority.P2),
    }
    if trigger.rule_id not in specifications:
        raise PumpStationWorkGenerationError("generation-rule", trigger.rule_id)
    work_type, closure_rule, priority = specifications[trigger.rule_id]
    generated_at = trigger.generated_at_calendar_seconds
    due_calendar: int | None = None
    due_runtime_kind: str | None = None
    due_runtime_id: str | None = None
    due_runtime_limit: int | None = None
    if trigger.rule_id in {"WG-01", "WG-02"}:
        candidates = [generated_at + 2 * D_CALENDAR_SECONDS]
        if trigger.next_capacity_critical_calendar_seconds is not None:
            candidates.append(trigger.next_capacity_critical_calendar_seconds)
            if trigger.next_capacity_critical_calendar_seconds <= generated_at + 2 * D_CALENDAR_SECONDS:
                priority = PumpStationPriority.P1
        due_calendar = min(candidates)
    elif trigger.rule_id == "WG-03":
        due_calendar = generated_at + 3_600
    elif trigger.rule_id == "WG-04":
        due_calendar = generated_at + 2 * D_CALENDAR_SECONDS
        due_runtime_kind = "pump_total"
        due_runtime_id = trigger.target_id
        due_runtime_limit = trigger.current_runtime_seconds + D_RUNTIME_SECONDS
    elif trigger.rule_id == "WG-05":
        due_calendar = generated_at + D_CALENDAR_SECONDS
        due_runtime_kind = "pump_total"
        due_runtime_id = trigger.target_id
        due_runtime_limit = trigger.current_runtime_seconds + D_RUNTIME_SECONDS
        if trigger.target_is_serving:
            priority = PumpStationPriority.P0
    elif trigger.rule_id == "WG-06":
        candidates = [generated_at + 1_209_600]
        if trigger.linked_clearance_due_calendar_seconds is not None:
            candidates.append(trigger.linked_clearance_due_calendar_seconds)
        due_calendar = min(candidates)
        if trigger.blocks_urgent_work:
            priority = PumpStationPriority.P1
    elif trigger.rule_id == "WG-07":
        due_calendar = generated_at + 2 * D_CALENDAR_SECONDS
        due_runtime_kind = "outage_episode_collateral"
        due_runtime_id = trigger.target_id
        due_runtime_limit = trigger.current_runtime_seconds + 2 * D_RUNTIME_SECONDS
    key = (
        trigger.rule_id,
        trigger.source_transition_id,
        trigger.target_kind,
        trigger.target_id,
        trigger.generation_ordinal,
    )
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
        stewardship_content_id,
    )

    item_id = f"backlog-{trigger.rule_id.lower()}-{stewardship_content_id(key)[:16]}"
    generation = PumpStationWorkGenerationRecord(
        rule_id=trigger.rule_id,
        source_transition_id=trigger.source_transition_id,
        target_kind=trigger.target_kind,
        target_id=trigger.target_id,
        generation_ordinal=trigger.generation_ordinal,
        backlog_item_id=item_id,
    )
    item = PumpStationBacklogItem(
        item_id=item_id,
        work_type=work_type,
        target_kind=trigger.target_kind,
        target_id=trigger.target_id,
        generation_rule_id=trigger.rule_id,
        generation_ordinal=trigger.generation_ordinal,
        originating_record_id=trigger.source_transition_id,
        linked_obligation_ids=trigger.linked_obligation_ids,
        linked_restriction_ids=trigger.linked_restriction_ids,
        linked_work_order_id=None,
        linked_process_id=None,
        generated_at_calendar_seconds=generated_at,
        base_priority=priority,
        effective_priority=priority,
        due_calendar_seconds=due_calendar,
        due_runtime_clock_kind=due_runtime_kind,
        due_runtime_clock_id=due_runtime_id,
        due_runtime_limit_seconds=due_runtime_limit,
        status=PumpStationBacklogStatus.OPEN,
        blocked_from_status=None,
        blocked_since_calendar_seconds=None,
        accumulated_blocked_seconds=0,
        closure_rule=closure_rule,
        closure_evidence_ids=(),
        supersedes_item_id=None,
        superseded_by_item_id=None,
    )
    return generate_work_once(records, backlog, generation, item)


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
