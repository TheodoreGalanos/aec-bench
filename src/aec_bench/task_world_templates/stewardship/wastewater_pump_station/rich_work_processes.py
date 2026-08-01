# ABOUTME: Applies dependency and resource rules for rich pump-station work processes.
# ABOUTME: Keeps reservation, suspension, resume, cancellation, and waiver effects deterministic.

from __future__ import annotations

from dataclasses import replace

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_events import (
    new_event,
    record_id,
    replace_process,
    replace_restriction,
    replace_work_order,
    sorted_events,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationAuthority,
    PumpStationDependencyKind,
    PumpStationDependencyWaiver,
    PumpStationEventType,
    PumpStationEvidenceKind,
    PumpStationProcess,
    PumpStationProcessDependency,
    PumpStationProcessKind,
    PumpStationProcessStatus,
    PumpStationProposalError,
    PumpStationResourceKind,
    PumpStationResourceReservation,
    PumpStationRestriction,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
    PumpStationWorkOrder,
    PumpStationWorkOrderStatus,
)

_LIVE_PROCESS_STATUSES = {
    PumpStationProcessStatus.BLOCKED,
    PumpStationProcessStatus.ACTIVE,
    PumpStationProcessStatus.SUSPENDED,
}
_TERMINAL_PROCESS_STATUSES = {
    PumpStationProcessStatus.COMPLETED,
    PumpStationProcessStatus.FAILED,
    PumpStationProcessStatus.INTERRUPTED,
    PumpStationProcessStatus.CANCELLED,
}


def is_rich_work_state(state: PumpStationStewardshipState) -> bool:
    """Return whether the state uses a rich-work contract."""
    return not state.state_version.endswith(".v1")


def resource_requirements(
    kind: PumpStationProcessKind,
) -> tuple[PumpStationResourceKind, ...]:
    """Return the fixed resource list for one approved process kind."""
    if kind is PumpStationProcessKind.OBSTRUCTION_CLEARANCE:
        return (
            PumpStationResourceKind.ACCESS,
            PumpStationResourceKind.REPAIR_KIT,
            PumpStationResourceKind.INTERVENTION_SLOT,
        )
    if kind in {
        PumpStationProcessKind.INSPECTION,
        PumpStationProcessKind.FUNCTIONAL_CHECKS,
        PumpStationProcessKind.POST_MAINTENANCE_VERIFICATION,
    }:
        return (
            PumpStationResourceKind.ACCESS,
            PumpStationResourceKind.INTERVENTION_SLOT,
        )
    return ()


def _reservation(
    state: PumpStationStewardshipState,
    kind: PumpStationResourceKind,
) -> PumpStationResourceReservation | None:
    return next(
        (item for item in state.resource_reservations if item.kind is kind),
        None,
    )


def _resource_available(
    state: PumpStationStewardshipState,
    kind: PumpStationResourceKind,
    process_id: str,
) -> bool:
    reservation = _reservation(state, kind)
    if reservation is not None and reservation.process_id != process_id:
        return False
    if kind is PumpStationResourceKind.ACCESS:
        return state.resources.access_window_seconds > 0
    if kind is PumpStationResourceKind.REPAIR_KIT:
        return state.resources.repair_kit_available
    return state.resources.available_intervention_slots > 0 or reservation is not None


def _accepted_evidence(
    state: PumpStationStewardshipState,
    evidence_id: str | None,
    *,
    kind: PumpStationEvidenceKind | None = None,
    pump_id: str | None = None,
) -> bool:
    if evidence_id is None:
        return False
    for evidence in state.evidence:
        if evidence.evidence_id != evidence_id:
            continue
        return (
            evidence.accepted_by is not None
            and (kind is None or evidence.kind is kind)
            and (pump_id is None or evidence.pump_id == pump_id)
        )
    return False


def _dependency_satisfied(
    state: PumpStationStewardshipState,
    process: PumpStationProcess,
    dependency: PumpStationProcessDependency,
) -> tuple[bool, str | None]:
    if dependency.kind is PumpStationDependencyKind.PHYSICAL:
        return process.pump_id in {pump.pump_id for pump in state.physical.pumps}, None
    if dependency.kind is PumpStationDependencyKind.SAFETY:
        if process.kind is PumpStationProcessKind.OBSTRUCTION_CLEARANCE:
            return state.physical.duty_pump_id != process.pump_id, None
        return True, None
    if dependency.kind is PumpStationDependencyKind.EVIDENCE:
        if process.kind is PumpStationProcessKind.OBSTRUCTION_CLEARANCE:
            satisfied = _accepted_evidence(
                state,
                process.source_evidence_id,
                kind=PumpStationEvidenceKind.INSPECTION,
                pump_id=process.pump_id,
            )
            return satisfied, process.source_evidence_id if satisfied else None
        return True, dependency.evidence_id
    if dependency.kind is PumpStationDependencyKind.ADMINISTRATIVE_CLOSEOUT:
        waived = next(
            (
                item
                for item in state.dependency_waivers
                if item.dependency_id == dependency.dependency_id and item.process_id == process.process_id
            ),
            None,
        )
        if waived is not None:
            return True, waived.evidence_id
        order = next(
            (item for item in state.work_orders if item.work_order_id == process.work_order_id),
            None,
        )
        return (
            order is not None and order.status is PumpStationWorkOrderStatus.PROVISIONALLY_CLOSED,
            None,
        )
    resource_kind = PumpStationResourceKind(dependency.detail)
    return _resource_available(state, resource_kind, process.process_id), None


def refresh_process_dependencies(
    state: PumpStationStewardshipState,
    process: PumpStationProcess,
) -> PumpStationStewardshipState:
    """Recompute every fixed dependency without changing its identity or order."""
    updates: list[PumpStationProcessDependency] = []
    for dependency in state.dependencies:
        if dependency.process_id != process.process_id:
            updates.append(dependency)
            continue
        satisfied, evidence_id = _dependency_satisfied(state, process, dependency)
        updates.append(
            replace(
                dependency,
                satisfied=satisfied,
                evidence_id=evidence_id,
            )
        )
    return replace(state, dependencies=tuple(updates))


def _new_dependencies(
    state: PumpStationStewardshipState,
    process: PumpStationProcess,
    sequence: int,
) -> tuple[PumpStationProcessDependency, ...]:
    kinds: list[tuple[PumpStationDependencyKind, str]] = [
        (PumpStationDependencyKind.PHYSICAL, "pump_exists"),
        (PumpStationDependencyKind.SAFETY, "pump_safe_for_work"),
    ]
    if process.kind is PumpStationProcessKind.OBSTRUCTION_CLEARANCE:
        kinds.append((PumpStationDependencyKind.EVIDENCE, "accepted_inspection"))
    if process.kind is PumpStationProcessKind.POST_MAINTENANCE_VERIFICATION:
        kinds.append(
            (
                PumpStationDependencyKind.ADMINISTRATIVE_CLOSEOUT,
                "work_order_closeout",
            )
        )
    kinds.extend(
        (PumpStationDependencyKind.RESOURCE, resource.value) for resource in resource_requirements(process.kind)
    )
    dependencies = tuple(
        PumpStationProcessDependency(
            dependency_id=record_id(
                "dependency",
                sequence,
                f"{process.kind.value}-{index:02d}",
            ),
            process_id=process.process_id,
            kind=kind,
            detail=detail,
            satisfied=False,
        )
        for index, (kind, detail) in enumerate(kinds, start=1)
    )
    candidate = replace(
        state,
        dependencies=(*state.dependencies, *dependencies),
    )
    refreshed = refresh_process_dependencies(candidate, process)
    return tuple(item for item in refreshed.dependencies if item.process_id == process.process_id)


def _all_dependencies_satisfied(
    state: PumpStationStewardshipState,
    process: PumpStationProcess,
) -> bool:
    dependencies = tuple(item for item in state.dependencies if item.process_id == process.process_id)
    return bool(dependencies) and all(item.satisfied for item in dependencies)


def _reserve_resources(
    state: PumpStationStewardshipState,
    process: PumpStationProcess,
    sequence: int,
) -> PumpStationStewardshipState:
    reservations = list(state.resource_reservations)
    slot_count = state.resources.available_intervention_slots
    for kind in resource_requirements(process.kind):
        existing = _reservation(state, kind)
        if existing is not None:
            if existing.process_id == process.process_id:
                continue
            raise PumpStationProposalError(
                "resource-reservation",
                f"{kind.value} is already reserved",
            )
        if not _resource_available(state, kind, process.process_id):
            raise PumpStationProposalError(
                "resource-reservation",
                f"{kind.value} is not available",
            )
        reservations.append(
            PumpStationResourceReservation(
                reservation_id=record_id(
                    "reservation",
                    sequence,
                    f"{process.process_id}-{kind.value}",
                ),
                kind=kind,
                process_id=process.process_id,
                created_sequence=sequence,
            )
        )
        if kind is PumpStationResourceKind.INTERVENTION_SLOT:
            slot_count -= 1
    return replace(
        state,
        resources=replace(
            state.resources,
            available_intervention_slots=slot_count,
        ),
        resource_reservations=tuple(reservations),
    )


def release_process_resources(
    state: PumpStationStewardshipState,
    process_id: str,
    *,
    keep_repair_kit: bool = False,
    consume_repair_kit: bool = False,
) -> PumpStationStewardshipState:
    """Release one process reservation set under the frozen resource rules."""
    retained: list[PumpStationResourceReservation] = []
    released_slot_count = 0
    released_kit = False
    for reservation in state.resource_reservations:
        if reservation.process_id != process_id:
            retained.append(reservation)
            continue
        if reservation.kind is PumpStationResourceKind.REPAIR_KIT and keep_repair_kit:
            retained.append(reservation)
            continue
        if reservation.kind is PumpStationResourceKind.INTERVENTION_SLOT:
            released_slot_count += 1
        if reservation.kind is PumpStationResourceKind.REPAIR_KIT:
            released_kit = True
    return replace(
        state,
        resources=replace(
            state.resources,
            available_intervention_slots=(state.resources.available_intervention_slots + released_slot_count),
            repair_kit_available=(
                False if consume_repair_kit and released_kit else state.resources.repair_kit_available
            ),
        ),
        resource_reservations=tuple(retained),
    )


def schedule_rich_process(
    state: PumpStationStewardshipState,
    *,
    sequence: int,
    kind: PumpStationProcessKind,
    pump_id: str,
    work_order: PumpStationWorkOrder,
    duration_seconds: int,
    performer: PumpStationAuthority,
    source_evidence_id: str | None = None,
) -> tuple[PumpStationStewardshipState, PumpStationProcess]:
    """Create one blocked or active process from fixed dependencies."""
    process = PumpStationProcess(
        process_id=record_id("process", sequence, kind.value),
        kind=kind,
        pump_id=pump_id,
        work_order_id=work_order.work_order_id,
        status=PumpStationProcessStatus.BLOCKED,
        started_at_seconds=state.physical.calendar_seconds,
        completion_at_seconds=state.physical.calendar_seconds + duration_seconds,
        performer=performer,
        source_evidence_id=source_evidence_id,
        remaining_duration_seconds=duration_seconds,
    )
    dependencies = _new_dependencies(state, process, sequence)
    process = replace(
        process,
        dependency_ids=tuple(item.dependency_id for item in dependencies),
    )
    candidate = replace(
        state,
        dependencies=(*state.dependencies, *dependencies),
        processes=(*state.processes, process),
        work_orders=replace_work_order(
            state.work_orders,
            replace(work_order, status=PumpStationWorkOrderStatus.SCHEDULED),
        ),
    )
    candidate = refresh_process_dependencies(candidate, process)
    if not _all_dependencies_satisfied(candidate, process):
        return candidate, process
    candidate = _reserve_resources(candidate, process, sequence)
    process = replace(process, status=PumpStationProcessStatus.ACTIVE)
    completion = new_event(
        sequence=sequence,
        suffix=f"{kind.value}-completion",
        event_type=PumpStationEventType.PROCESS_COMPLETION,
        scheduled_seconds=process.completion_at_seconds,
        process_id=process.process_id,
    )
    candidate = replace(
        candidate,
        processes=replace_process(candidate.processes, process),
        work_orders=replace_work_order(
            candidate.work_orders,
            replace(work_order, status=PumpStationWorkOrderStatus.IN_PROGRESS),
        ),
        scheduled_events=sorted_events((*candidate.scheduled_events, completion)),
    )
    return candidate, process


def resume_process(
    state: PumpStationStewardshipState,
    process_id: str,
    sequence: int,
) -> tuple[PumpStationStewardshipState, PumpStationProcess] | None:
    """Resume blocked or suspended work only when every dependency is satisfied."""
    process = state.process(process_id)
    if process.status not in {
        PumpStationProcessStatus.BLOCKED,
        PumpStationProcessStatus.SUSPENDED,
    }:
        raise PumpStationProposalError(
            "process-state",
            "only blocked or suspended work can resume",
        )
    candidate = refresh_process_dependencies(state, process)
    process = candidate.process(process_id)
    if not _all_dependencies_satisfied(candidate, process):
        return None
    candidate = _reserve_resources(candidate, process, sequence)
    remaining = process.remaining_duration_seconds
    if remaining is None:
        remaining = max(
            0,
            process.completion_at_seconds - state.physical.calendar_seconds,
        )
    resumed = replace(
        process,
        status=PumpStationProcessStatus.ACTIVE,
        completion_at_seconds=state.physical.calendar_seconds + remaining,
        suspended_at_seconds=None,
    )
    completion = new_event(
        sequence=sequence,
        suffix=f"{process.kind.value}-completion",
        event_type=PumpStationEventType.PROCESS_COMPLETION,
        scheduled_seconds=resumed.completion_at_seconds,
        process_id=process.process_id,
    )
    order = next(item for item in candidate.work_orders if item.work_order_id == process.work_order_id)
    return (
        replace(
            candidate,
            processes=replace_process(candidate.processes, resumed),
            work_orders=replace_work_order(
                candidate.work_orders,
                replace(order, status=PumpStationWorkOrderStatus.IN_PROGRESS),
            ),
            scheduled_events=sorted_events((*candidate.scheduled_events, completion)),
        ),
        resumed,
    )


def cancel_process(
    state: PumpStationStewardshipState,
    process_id: str,
) -> tuple[PumpStationStewardshipState, PumpStationProcess]:
    """Cancel live work and release all unused process resources."""
    process = state.process(process_id)
    if process.status not in _LIVE_PROCESS_STATUSES:
        raise PumpStationProposalError("process-state", "only live work can be cancelled")
    candidate = release_process_resources(state, process_id)
    cancelled = replace(
        process,
        status=PumpStationProcessStatus.CANCELLED,
        remaining_duration_seconds=max(
            0,
            process.completion_at_seconds - state.physical.calendar_seconds,
        ),
        cancelled_at_seconds=state.physical.calendar_seconds,
    )
    return (
        replace(
            candidate,
            processes=replace_process(candidate.processes, cancelled),
            scheduled_events=tuple(event for event in candidate.scheduled_events if event.process_id != process_id),
        ),
        cancelled,
    )


def suspend_access_dependent_processes(
    state: PumpStationStewardshipState,
    sequence: int,
) -> tuple[PumpStationStewardshipState, tuple[str, ...], tuple[str, ...]]:
    """Suspend active access work and create child no-intervention limits."""
    candidate = state
    changed_processes: list[str] = []
    changed_restrictions: list[str] = []
    now = state.physical.calendar_seconds
    for process in state.processes:
        if (
            process.status is not PumpStationProcessStatus.ACTIVE
            or PumpStationResourceKind.ACCESS not in resource_requirements(process.kind)
        ):
            continue
        remaining = max(0, process.completion_at_seconds - now)
        suspended = replace(
            process,
            status=PumpStationProcessStatus.SUSPENDED,
            remaining_duration_seconds=remaining,
            suspended_at_seconds=now,
        )
        candidate = replace(
            candidate,
            processes=replace_process(candidate.processes, suspended),
            scheduled_events=tuple(
                event for event in candidate.scheduled_events if event.process_id != process.process_id
            ),
        )
        candidate = release_process_resources(
            candidate,
            process.process_id,
            keep_repair_kit=True,
        )
        changed_processes.append(process.process_id)
        parent = next(
            (
                item
                for item in reversed(candidate.restrictions)
                if item.pump_id == process.pump_id
                and item.status is PumpStationRestrictionStatus.ACTIVE
                and item.parent_restriction_id is None
            ),
            None,
        )
        if parent is None:
            continue
        existing_child = next(
            (
                item
                for item in candidate.restrictions
                if item.parent_restriction_id == parent.restriction_id
                and item.kind is PumpStationRestrictionKind.NO_INTERVENTION
                and item.status is PumpStationRestrictionStatus.ACTIVE
            ),
            None,
        )
        if existing_child is not None:
            continue
        child = PumpStationRestriction(
            restriction_id=record_id(
                "restriction",
                sequence,
                f"no-intervention-{process.process_id}",
            ),
            kind=PumpStationRestrictionKind.NO_INTERVENTION,
            pump_id=process.pump_id,
            status=PumpStationRestrictionStatus.ACTIVE,
            created_sequence=sequence,
            parent_restriction_id=parent.restriction_id,
        )
        candidate = replace(
            candidate,
            restrictions=(*candidate.restrictions, child),
        )
        changed_restrictions.append(child.restriction_id)
    return candidate, tuple(changed_processes), tuple(changed_restrictions)


def lift_access_restrictions(
    state: PumpStationStewardshipState,
    evidence_id: str,
) -> tuple[PumpStationStewardshipState, tuple[str, ...]]:
    """Lift only child no-intervention limits when access returns."""
    restrictions = state.restrictions
    changed: list[str] = []
    for restriction in state.restrictions:
        if (
            restriction.kind is PumpStationRestrictionKind.NO_INTERVENTION
            and restriction.status is PumpStationRestrictionStatus.ACTIVE
        ):
            lifted = replace(
                restriction,
                status=PumpStationRestrictionStatus.LIFTED,
                evidence_id=evidence_id,
            )
            restrictions = replace_restriction(restrictions, lifted)
            changed.append(restriction.restriction_id)
    return replace(state, restrictions=restrictions), tuple(changed)


def apply_dependency_waiver(
    state: PumpStationStewardshipState,
    *,
    process_id: str,
    dependency_id: str,
    evidence_id: str,
    sequence: int,
) -> tuple[PumpStationStewardshipState, PumpStationDependencyWaiver]:
    """Record one approved administrative waiver without completing work."""
    dependency = state.dependency(dependency_id)
    if dependency.process_id != process_id:
        raise PumpStationProposalError(
            "dependency-waiver",
            "dependency belongs to another process",
        )
    if dependency.kind is not PumpStationDependencyKind.ADMINISTRATIVE_CLOSEOUT:
        raise PumpStationProposalError(
            "dependency-waiver",
            "only administrative closeout can be waived",
        )
    if not _accepted_evidence(state, evidence_id):
        raise PumpStationProposalError(
            "dependency-waiver",
            "named accepted evidence is not available",
        )
    waiver = PumpStationDependencyWaiver(
        waiver_id=record_id("waiver", sequence, dependency_id),
        process_id=process_id,
        dependency_id=dependency_id,
        evidence_id=evidence_id,
        approved_by=PumpStationAuthority.WORK_MANAGEMENT,
        created_sequence=sequence,
    )
    return replace(
        state,
        dependency_waivers=(*state.dependency_waivers, waiver),
    ), waiver


def terminal_process_event(state: PumpStationStewardshipState, process_id: str) -> bool:
    """Return whether a late completion event must have no effect."""
    return state.process(process_id).status in _TERMINAL_PROCESS_STATUSES
