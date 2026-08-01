# ABOUTME: Applies scheduled work, resource, and obligation events for the pump station.
# ABOUTME: Keeps deterministic event order and process completion separate from proposal policy.

from __future__ import annotations

from dataclasses import replace

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PumpStationEvidenceHealth,
    PumpStationEvidenceQuality,
    PumpStationEvidenceTreatment,
    PumpStationEvidenceTreatmentClass,
    PumpStationEvidenceTreatmentStatus,
    PumpStationObservationSource,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    apply_pump_intervention,
    assess_pump_station,
    inspect_pump,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpIntervention,
    PumpInterventionKind,
    PumpStationChangeKind,
    PumpStationModel,
    PumpStationResources,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationAuthority,
    PumpStationEventType,
    PumpStationEvidence,
    PumpStationEvidenceKind,
    PumpStationExecutionOutcome,
    PumpStationObligation,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationProcess,
    PumpStationProcessKind,
    PumpStationProcessStatus,
    PumpStationProposalError,
    PumpStationResourceKind,
    PumpStationRestriction,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    PumpStationScheduledEvent,
    PumpStationStewardshipState,
    PumpStationWorkOrder,
    PumpStationWorkOrderStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_policy import (
    current_obligation,
    work_order,
)

_EVENT_PRIORITY = {
    PumpStationEventType.EVIDENCE_TREATMENT_ACTIVATION: 1,
    PumpStationEventType.EVIDENCE_RELEASE: 2,
    PumpStationEventType.OBLIGATION_DUE: 3,
    PumpStationEventType.OBLIGATION_OVERDUE: 3,
    PumpStationEventType.OBLIGATION_BREACH: 3,
    PumpStationEventType.ACCESS_AVAILABLE: 4,
    PumpStationEventType.ACCESS_WITHDRAWN: 4,
    PumpStationEventType.REPAIR_KIT_AVAILABLE: 4,
    PumpStationEventType.PROCESS_COMPLETION: 6,
    PumpStationEventType.DECISION_POINT: 8,
}


def event_sort_key(
    event: PumpStationScheduledEvent,
) -> tuple[int, int, str]:
    """Return the canonical time, class, and identity ordering key."""
    return (
        event.scheduled_seconds,
        _EVENT_PRIORITY[event.event_type],
        event.event_id,
    )


def sorted_events(
    events: tuple[PumpStationScheduledEvent, ...],
) -> tuple[PumpStationScheduledEvent, ...]:
    """Return events in canonical scheduler order."""
    return tuple(sorted(events, key=event_sort_key))


def record_id(kind: str, sequence: int, suffix: str) -> str:
    """Create a deterministic task-local record identity."""
    return f"{kind}-{sequence:04d}-{suffix}"


def new_event(
    *,
    sequence: int,
    suffix: str,
    event_type: PumpStationEventType,
    scheduled_seconds: int,
    process_id: str | None = None,
    obligation_id: str | None = None,
    treatment_id: str | None = None,
    evidence_id: str | None = None,
) -> PumpStationScheduledEvent:
    """Create one deterministic scheduled event."""
    return PumpStationScheduledEvent(
        event_id=record_id("event", sequence, suffix),
        event_type=event_type,
        scheduled_seconds=scheduled_seconds,
        process_id=process_id,
        obligation_id=obligation_id,
        treatment_id=treatment_id,
        evidence_id=evidence_id,
    )


def _replace_source(
    sources: tuple[PumpStationObservationSource, ...],
    updated: PumpStationObservationSource,
) -> tuple[PumpStationObservationSource, ...]:
    return tuple(updated if item.source_id == updated.source_id else item for item in sources)


def _replace_treatment(
    treatments: tuple[PumpStationEvidenceTreatment, ...],
    updated: PumpStationEvidenceTreatment,
) -> tuple[PumpStationEvidenceTreatment, ...]:
    return tuple(updated if item.treatment_id == updated.treatment_id else item for item in treatments)


def _find_treatment(
    treatments: tuple[PumpStationEvidenceTreatment, ...],
    treatment_id: str,
) -> PumpStationEvidenceTreatment:
    for treatment in treatments:
        if treatment.treatment_id == treatment_id:
            return treatment
    raise PumpStationProposalError(
        "scheduled-event",
        f"missing evidence treatment {treatment_id}",
    )


def _find_source(
    sources: tuple[PumpStationObservationSource, ...],
    source_id: str,
) -> PumpStationObservationSource:
    for source in sources:
        if source.source_id == source_id:
            return source
    raise PumpStationProposalError(
        "scheduled-event",
        f"missing observation source {source_id}",
    )


def replace_restriction(
    restrictions: tuple[PumpStationRestriction, ...],
    updated: PumpStationRestriction,
) -> tuple[PumpStationRestriction, ...]:
    """Replace one restriction without changing tuple order."""
    return tuple(updated if item.restriction_id == updated.restriction_id else item for item in restrictions)


def replace_obligation(
    obligations: tuple[PumpStationObligation, ...],
    updated: PumpStationObligation,
) -> tuple[PumpStationObligation, ...]:
    """Replace one obligation without changing tuple order."""
    return tuple(updated if item.obligation_id == updated.obligation_id else item for item in obligations)


def replace_work_order(
    work_orders: tuple[PumpStationWorkOrder, ...],
    updated: PumpStationWorkOrder,
) -> tuple[PumpStationWorkOrder, ...]:
    """Replace one work order without changing tuple order."""
    return tuple(updated if item.work_order_id == updated.work_order_id else item for item in work_orders)


def replace_process(
    processes: tuple[PumpStationProcess, ...],
    updated: PumpStationProcess,
) -> tuple[PumpStationProcess, ...]:
    """Replace one process without changing tuple order."""
    return tuple(updated if item.process_id == updated.process_id else item for item in processes)


def _remove_obligation_events(
    events: tuple[PumpStationScheduledEvent, ...],
    obligation_id: str,
) -> tuple[PumpStationScheduledEvent, ...]:
    return tuple(event for event in events if event.obligation_id != obligation_id)


def schedule_process(
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
    """Start one timed process and schedule its completion."""
    process = PumpStationProcess(
        process_id=record_id("process", sequence, kind.value),
        kind=kind,
        pump_id=pump_id,
        work_order_id=work_order.work_order_id,
        status=PumpStationProcessStatus.IN_PROGRESS,
        started_at_seconds=state.physical.calendar_seconds,
        completion_at_seconds=(state.physical.calendar_seconds + duration_seconds),
        performer=performer,
        source_evidence_id=source_evidence_id,
    )
    completion = new_event(
        sequence=sequence,
        suffix=f"{kind.value}-completion",
        event_type=PumpStationEventType.PROCESS_COMPLETION,
        scheduled_seconds=process.completion_at_seconds,
        process_id=process.process_id,
    )
    updated_order = replace(
        work_order,
        status=PumpStationWorkOrderStatus.IN_PROGRESS,
    )
    return (
        replace(
            state,
            processes=(*state.processes, process),
            work_orders=replace_work_order(
                state.work_orders,
                updated_order,
            ),
            scheduled_events=sorted_events((*state.scheduled_events, completion)),
        ),
        process,
    )


def _find_process(
    processes: tuple[PumpStationProcess, ...],
    process_id: str,
) -> PumpStationProcess:
    for process in processes:
        if process.process_id == process_id:
            return process
    raise PumpStationProposalError(
        "scheduled-event",
        f"missing process {process_id}",
    )


def _find_obligation(
    obligations: tuple[PumpStationObligation, ...],
    obligation_id: str,
) -> PumpStationObligation:
    for obligation in obligations:
        if obligation.obligation_id == obligation_id:
            return obligation
    raise PumpStationProposalError(
        "scheduled-event",
        f"missing obligation {obligation_id}",
    )


def _complete_inspection(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    process: PumpStationProcess,
    sequence: int,
) -> tuple[PumpStationStewardshipState, str, tuple[str, ...]]:
    inspection = inspect_pump(model, state.physical, process.pump_id)
    evidence = PumpStationEvidence(
        evidence_id=record_id("evidence", sequence, "inspection"),
        kind=PumpStationEvidenceKind.INSPECTION,
        pump_id=process.pump_id,
        created_at_seconds=state.physical.calendar_seconds,
        produced_by=PumpStationAuthority.MAINTENANCE,
        accepted_by=PumpStationAuthority.ENGINEERING,
        health=_completed_evidence_health(
            state,
            source_id="physical-inspection",
            pump_id=process.pump_id,
            baseline_id=f"{process.pump_id}-physical-condition.v1",
            accepted=True,
        ),
        inspection=inspection,
    )
    completed = replace(process, status=PumpStationProcessStatus.COMPLETED)
    obligations = state.obligations
    obligation_changes: tuple[str, ...] = ()
    scheduled_events = state.scheduled_events
    follow_up = current_obligation(
        state,
        PumpStationObligationKind.DEFERRED_FOLLOW_UP,
        process.pump_id,
    )
    if follow_up is not None and follow_up.status in {
        PumpStationObligationStatus.ACTIVE,
        PumpStationObligationStatus.DUE,
        PumpStationObligationStatus.OVERDUE,
    }:
        fulfilled = replace(
            follow_up,
            status=PumpStationObligationStatus.FULFILLED,
            evidence_id=evidence.evidence_id,
        )
        obligations = replace_obligation(obligations, fulfilled)
        obligation_changes = (fulfilled.obligation_id,)
        scheduled_events = _remove_obligation_events(
            scheduled_events,
            fulfilled.obligation_id,
        )
    return (
        replace(
            state,
            processes=replace_process(state.processes, completed),
            evidence=(*state.evidence, evidence),
            obligations=obligations,
            scheduled_events=scheduled_events,
        ),
        evidence.evidence_id,
        obligation_changes,
    )


def _complete_obstruction_clearance(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    process: PumpStationProcess,
    sequence: int,
) -> tuple[
    PumpStationStewardshipState,
    PumpStationExecutionOutcome,
    PumpStationChangeKind | None,
    tuple[str, ...],
]:
    rich_work = not state.state_version.endswith(".v1")
    if not rich_work and (
        state.resources.access_window_seconds < model.resources.access_duration_seconds
        or state.resources.available_intervention_slots < 1
    ):
        interrupted = replace(
            process,
            status=PumpStationProcessStatus.INTERRUPTED,
        )
        return (
            replace(
                state,
                processes=replace_process(
                    state.processes,
                    interrupted,
                ),
            ),
            PumpStationExecutionOutcome.INTERRUPTED,
            None,
            (interrupted.process_id,),
        )
    reserved_slot = any(
        item.kind is PumpStationResourceKind.INTERVENTION_SLOT and item.process_id == process.process_id
        for item in state.resource_reservations
    )
    physical = apply_pump_intervention(
        model,
        state.physical,
        PumpIntervention(
            kind=PumpInterventionKind.CLEAR_OBSTRUCTION,
            pump_id=process.pump_id,
        ),
        PumpStationResources(
            access_window_seconds=state.resources.access_window_seconds,
            repair_kit_available=state.resources.repair_kit_available,
            available_intervention_slots=(state.resources.available_intervention_slots + int(reserved_slot)),
        ),
        state.environment,
    )
    completed = replace(process, status=PumpStationProcessStatus.COMPLETED)
    order = work_order(state, process.work_order_id)
    if order is None:
        raise PumpStationProposalError(
            "stewardship-state",
            "clearance process lost its work order",
        )
    candidate = replace(
        state,
        physical=physical.state,
        processes=replace_process(state.processes, completed),
    )
    if rich_work:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rich_work_processes import (
            schedule_rich_process,
        )

        candidate, checks = schedule_rich_process(
            candidate,
            sequence=sequence,
            kind=PumpStationProcessKind.FUNCTIONAL_CHECKS,
            pump_id=process.pump_id,
            work_order=order,
            duration_seconds=model.resources.access_duration_seconds // 4,
            performer=PumpStationAuthority.MAINTENANCE,
        )
    else:
        candidate, checks = schedule_process(
            candidate,
            sequence=sequence,
            kind=PumpStationProcessKind.FUNCTIONAL_CHECKS,
            pump_id=process.pump_id,
            work_order=order,
            duration_seconds=model.resources.access_duration_seconds // 4,
            performer=PumpStationAuthority.MAINTENANCE,
        )
    return (
        candidate,
        PumpStationExecutionOutcome.COMPLETED,
        physical.change_kind,
        (completed.process_id, checks.process_id),
    )


def _complete_functional_checks(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    process: PumpStationProcess,
    sequence: int,
) -> tuple[PumpStationStewardshipState, str, tuple[str, ...]]:
    assessment = assess_pump_station(model, state.physical, state.environment)
    passed = not assessment.capability.review_required
    evidence = PumpStationEvidence(
        evidence_id=record_id("evidence", sequence, "functional-checks"),
        kind=PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
        pump_id=process.pump_id,
        created_at_seconds=state.physical.calendar_seconds,
        produced_by=PumpStationAuthority.MAINTENANCE,
        accepted_by=(PumpStationAuthority.VERIFICATION if passed else None),
        passed=passed,
        health=_completed_evidence_health(
            state,
            source_id="maintenance-functional-checks",
            pump_id=process.pump_id,
            baseline_id=f"{process.pump_id}-post-maintenance-baseline.v1",
            accepted=passed,
        ),
    )
    updated_process = replace(
        process,
        status=(PumpStationProcessStatus.COMPLETED if passed else PumpStationProcessStatus.FAILED),
    )
    order = work_order(state, process.work_order_id)
    if order is None:
        raise PumpStationProposalError(
            "stewardship-state",
            "functional checks lost their work order",
        )
    updated_order = replace(
        order,
        status=(PumpStationWorkOrderStatus.SCOPE_COMPLETED if passed else PumpStationWorkOrderStatus.OPEN),
    )
    return (
        replace(
            state,
            processes=replace_process(state.processes, updated_process),
            work_orders=replace_work_order(
                state.work_orders,
                updated_order,
            ),
            evidence=(*state.evidence, evidence),
        ),
        evidence.evidence_id,
        (updated_order.work_order_id,),
    )


def _complete_verification(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    process: PumpStationProcess,
    sequence: int,
) -> tuple[
    PumpStationStewardshipState,
    str,
    tuple[str, ...],
    tuple[str, ...],
]:
    assessment = assess_pump_station(model, state.physical, state.environment)
    passed = not assessment.capability.review_required
    evidence = PumpStationEvidence(
        evidence_id=record_id("evidence", sequence, "verification"),
        kind=PumpStationEvidenceKind.POST_MAINTENANCE_VERIFICATION,
        pump_id=process.pump_id,
        created_at_seconds=state.physical.calendar_seconds,
        produced_by=PumpStationAuthority.VERIFICATION,
        accepted_by=PumpStationAuthority.VERIFICATION,
        passed=passed,
        health=_completed_evidence_health(
            state,
            source_id="independent-verification",
            pump_id=process.pump_id,
            baseline_id=f"{process.pump_id}-post-maintenance-baseline.v1",
            accepted=True,
        ),
    )
    updated_process = replace(
        process,
        status=(PumpStationProcessStatus.COMPLETED if passed else PumpStationProcessStatus.FAILED),
    )
    obligation = current_obligation(
        state,
        PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
        process.pump_id,
    )
    obligation_changes: tuple[str, ...] = ()
    obligations = state.obligations
    scheduled_events = state.scheduled_events
    if obligation is not None and passed:
        fulfilled = replace(
            obligation,
            status=PumpStationObligationStatus.FULFILLED,
            evidence_id=evidence.evidence_id,
        )
        obligations = replace_obligation(obligations, fulfilled)
        obligation_changes = (fulfilled.obligation_id,)
        scheduled_events = _remove_obligation_events(
            scheduled_events,
            fulfilled.obligation_id,
        )
    work_orders = state.work_orders
    work_order_changes: tuple[str, ...] = ()
    if not passed:
        order = work_order(state, process.work_order_id)
        if order is not None:
            reopened = replace(order, status=PumpStationWorkOrderStatus.OPEN)
            work_orders = replace_work_order(work_orders, reopened)
            work_order_changes = (reopened.work_order_id,)
    return (
        replace(
            state,
            processes=replace_process(state.processes, updated_process),
            obligations=obligations,
            scheduled_events=scheduled_events,
            work_orders=work_orders,
            evidence=(*state.evidence, evidence),
        ),
        evidence.evidence_id,
        obligation_changes,
        work_order_changes,
    )


def _completed_evidence_health(
    state: PumpStationStewardshipState,
    *,
    source_id: str,
    pump_id: str,
    baseline_id: str,
    accepted: bool,
) -> PumpStationEvidenceHealth | None:
    if not state.state_version.endswith(".v3"):
        return None
    now = state.physical.calendar_seconds
    return PumpStationEvidenceHealth(
        observed_at_seconds=now,
        produced_at_seconds=now,
        available_at_seconds=now,
        source_id=source_id,
        component_scope=(pump_id,),
        baseline_id=baseline_id,
        operating_regime_id=(f"{state.physical.duty_pump_id}-duty-{state.physical.standby_pump_id}-standby.v1"),
        accepted=accepted,
        quality=PumpStationEvidenceQuality.CURRENT,
    )


def apply_scheduled_event(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    event: PumpStationScheduledEvent,
    sequence: int,
) -> tuple[
    PumpStationStewardshipState,
    PumpStationExecutionOutcome,
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    PumpStationChangeKind | None,
]:
    """Apply one event after the scheduler has advanced physical time."""
    process_changes: tuple[str, ...] = ()
    restriction_changes: tuple[str, ...] = ()
    obligation_changes: tuple[str, ...] = ()
    work_order_changes: tuple[str, ...] = ()
    evidence_created: tuple[str, ...] = ()
    evidence_sources_changed: tuple[str, ...] = ()
    evidence_treatments_changed: tuple[str, ...] = ()
    physical_change: PumpStationChangeKind | None = None
    execution = PumpStationExecutionOutcome.COMPLETED
    rich_work = not state.state_version.endswith(".v1")
    if event.event_type is PumpStationEventType.DECISION_POINT:
        sources = state.evidence_sources
        for source in state.evidence_sources:
            if not source.refresh_enabled or not source.reading_available:
                continue
            assessment = assess_pump_station(model, state.physical, state.environment)
            updated_source = replace(
                source,
                observation=assessment.observation,
                observed_at_seconds=state.physical.calendar_seconds,
                produced_at_seconds=state.physical.calendar_seconds,
                available_at_seconds=state.physical.calendar_seconds,
                operating_regime_id=(f"{state.physical.duty_pump_id}-duty-{state.physical.standby_pump_id}-standby.v1"),
            )
            sources = _replace_source(sources, updated_source)
            evidence_sources_changed = (*evidence_sources_changed, source.source_id)
        state = replace(state, evidence_sources=sources)
    elif event.event_type is PumpStationEventType.EVIDENCE_TREATMENT_ACTIVATION:
        if event.treatment_id is None:
            raise PumpStationProposalError(
                "scheduled-event",
                "treatment activation has no treatment identity",
            )
        treatment = _find_treatment(state.evidence_treatments, event.treatment_id)
        if treatment.status is not PumpStationEvidenceTreatmentStatus.SCHEDULED:
            raise PumpStationProposalError(
                "scheduled-event",
                "treatment activation is not scheduled",
            )
        source = _find_source(
            state.evidence_sources,
            treatment.request.target_source_id,
        )
        treatment_class = treatment.request.treatment_class
        updated_source = source
        if treatment_class is PumpStationEvidenceTreatmentClass.CALIBRATION_LAPSE:
            updated_source = replace(source, quality=PumpStationEvidenceQuality.SUSPECT)
        elif treatment_class is PumpStationEvidenceTreatmentClass.STALE_SAMPLE:
            updated_source = replace(source, refresh_enabled=False)
        elif treatment_class is PumpStationEvidenceTreatmentClass.OBSERVATION_LOSS:
            updated_source = replace(
                source,
                quality=PumpStationEvidenceQuality.UNAVAILABLE,
                reading_available=False,
            )
        elif treatment_class is PumpStationEvidenceTreatmentClass.BASELINE_CHANGE:
            updated_source = replace(
                source,
                baseline_id="station-condition-baseline.v2",
            )
        updated_treatment = replace(
            treatment,
            status=PumpStationEvidenceTreatmentStatus.ACTIVE,
            activated_sequence=sequence,
            activated_at_seconds=state.physical.calendar_seconds,
        )
        state = replace(
            state,
            evidence_sources=_replace_source(
                state.evidence_sources,
                updated_source,
            ),
            evidence_treatments=_replace_treatment(
                state.evidence_treatments,
                updated_treatment,
            ),
        )
        if updated_source != source:
            evidence_sources_changed = (source.source_id,)
        evidence_treatments_changed = (treatment.treatment_id,)
    elif event.event_type is PumpStationEventType.EVIDENCE_RELEASE:
        if event.evidence_id is None:
            raise PumpStationProposalError(
                "scheduled-event",
                "evidence release has no evidence identity",
            )
        pending = next(
            (item for item in state.pending_evidence if item.evidence.evidence_id == event.evidence_id),
            None,
        )
        if pending is None or pending.release_at_seconds != state.physical.calendar_seconds:
            raise PumpStationProposalError(
                "scheduled-event",
                f"missing pending evidence {event.evidence_id}",
            )
        state = replace(
            state,
            evidence=(*state.evidence, pending.evidence),
            pending_evidence=tuple(
                item for item in state.pending_evidence if item.evidence.evidence_id != event.evidence_id
            ),
        )
        evidence_created = (pending.evidence.evidence_id,)
    elif event.event_type is PumpStationEventType.ACCESS_AVAILABLE:
        state = replace(
            state,
            resources=replace(
                state.resources,
                access_window_seconds=model.resources.access_duration_seconds,
            ),
        )
        if event.process_id is not None:
            process = _find_process(state.processes, event.process_id)
            if process.status in {
                PumpStationProcessStatus.ACTIVE,
                PumpStationProcessStatus.IN_PROGRESS,
            }:
                completed = replace(
                    process,
                    status=PumpStationProcessStatus.COMPLETED,
                    remaining_duration_seconds=0,
                )
                state = replace(
                    state,
                    processes=replace_process(state.processes, completed),
                )
                process_changes = (process.process_id,)
        if rich_work:
            from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rich_work_processes import (
                lift_access_restrictions,
            )

            state, lifted = lift_access_restrictions(state, event.event_id)
            restriction_changes = (*restriction_changes, *lifted)
    elif event.event_type is PumpStationEventType.ACCESS_WITHDRAWN:
        state = replace(
            state,
            resources=replace(state.resources, access_window_seconds=0),
        )
        if rich_work:
            from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rich_work_processes import (
                suspend_access_dependent_processes,
            )

            state, suspended, restricted = suspend_access_dependent_processes(
                state,
                sequence,
            )
            process_changes = (*process_changes, *suspended)
            restriction_changes = (*restriction_changes, *restricted)
    elif event.event_type is PumpStationEventType.REPAIR_KIT_AVAILABLE:
        state = replace(
            state,
            resources=replace(state.resources, repair_kit_available=True),
        )
        if event.process_id is not None:
            process = _find_process(state.processes, event.process_id)
            if process.status in {
                PumpStationProcessStatus.ACTIVE,
                PumpStationProcessStatus.IN_PROGRESS,
            }:
                completed = replace(
                    process,
                    status=PumpStationProcessStatus.COMPLETED,
                    remaining_duration_seconds=0,
                )
                state = replace(
                    state,
                    processes=replace_process(state.processes, completed),
                )
                process_changes = (process.process_id,)
    elif event.event_type in {
        PumpStationEventType.OBLIGATION_DUE,
        PumpStationEventType.OBLIGATION_OVERDUE,
        PumpStationEventType.OBLIGATION_BREACH,
    }:
        if event.obligation_id is None:
            raise PumpStationProposalError(
                "scheduled-event",
                "obligation event has no obligation identity",
            )
        obligation = _find_obligation(
            state.obligations,
            event.obligation_id,
        )
        target_status = {
            PumpStationEventType.OBLIGATION_DUE: (PumpStationObligationStatus.DUE),
            PumpStationEventType.OBLIGATION_OVERDUE: (PumpStationObligationStatus.OVERDUE),
            PumpStationEventType.OBLIGATION_BREACH: (PumpStationObligationStatus.BREACHED),
        }[event.event_type]
        permitted_previous = {
            PumpStationEventType.OBLIGATION_DUE: {PumpStationObligationStatus.ACTIVE},
            PumpStationEventType.OBLIGATION_OVERDUE: {PumpStationObligationStatus.DUE},
            PumpStationEventType.OBLIGATION_BREACH: {
                PumpStationObligationStatus.ACTIVE,
                PumpStationObligationStatus.DUE,
                PumpStationObligationStatus.OVERDUE,
            },
        }[event.event_type]
        if obligation.status in permitted_previous:
            updated = replace(obligation, status=target_status)
            state = replace(
                state,
                obligations=replace_obligation(
                    state.obligations,
                    updated,
                ),
            )
            obligation_changes = (updated.obligation_id,)
    else:
        if event.process_id is None:
            raise PumpStationProposalError(
                "scheduled-event",
                "process event has no process identity",
            )
        process = _find_process(state.processes, event.process_id)
        if rich_work and process.status in {
            PumpStationProcessStatus.COMPLETED,
            PumpStationProcessStatus.FAILED,
            PumpStationProcessStatus.INTERRUPTED,
            PumpStationProcessStatus.CANCELLED,
        }:
            return (
                state,
                execution,
                (),
                (),
                (),
                (),
                (),
                (),
                (),
                None,
            )
        if rich_work and process.status is not PumpStationProcessStatus.ACTIVE:
            return (
                state,
                execution,
                (),
                (),
                (),
                (),
                (),
                (),
                (),
                None,
            )
        if process.kind is PumpStationProcessKind.INSPECTION:
            state, evidence_id, obligation_changes = _complete_inspection(
                model,
                state,
                process,
                sequence,
            )
            process_changes = (process.process_id,)
            evidence_created = (evidence_id,)
        elif process.kind is PumpStationProcessKind.OBSTRUCTION_CLEARANCE:
            (
                state,
                execution,
                physical_change,
                process_changes,
            ) = _complete_obstruction_clearance(
                model,
                state,
                process,
                sequence,
            )
            if len(process_changes) > 1:
                work_order_changes = (process.work_order_id,)
        elif process.kind is PumpStationProcessKind.FUNCTIONAL_CHECKS:
            state, evidence_id, work_order_changes = _complete_functional_checks(
                model,
                state,
                process,
                sequence,
            )
            process_changes = (process.process_id,)
            evidence_created = (evidence_id,)
            updated_process = _find_process(state.processes, process.process_id)
            if updated_process.status is PumpStationProcessStatus.FAILED:
                execution = PumpStationExecutionOutcome.FAILED
        else:
            (
                state,
                evidence_id,
                obligation_changes,
                work_order_changes,
            ) = _complete_verification(
                model,
                state,
                process,
                sequence,
            )
            process_changes = (process.process_id,)
            evidence_created = (evidence_id,)
            updated_process = _find_process(state.processes, process.process_id)
            if updated_process.status is PumpStationProcessStatus.FAILED:
                execution = PumpStationExecutionOutcome.FAILED
        if rich_work:
            from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rich_work_processes import (
                release_process_resources,
                resume_process,
            )

            successful_clearance = (
                process.kind is PumpStationProcessKind.OBSTRUCTION_CLEARANCE
                and execution is PumpStationExecutionOutcome.COMPLETED
            )
            state = release_process_resources(
                state,
                process.process_id,
                consume_repair_kit=successful_clearance,
            )
            if successful_clearance:
                checks = next(
                    (
                        item
                        for item in reversed(state.processes)
                        if item.kind is PumpStationProcessKind.FUNCTIONAL_CHECKS
                        and item.pump_id == process.pump_id
                        and item.status is PumpStationProcessStatus.BLOCKED
                    ),
                    None,
                )
                if checks is not None:
                    resumed = resume_process(state, checks.process_id, sequence)
                    if resumed is not None:
                        state, active_checks = resumed
                        process_changes = (*process_changes, active_checks.process_id)
            if process.kind is PumpStationProcessKind.POST_MAINTENANCE_VERIFICATION and evidence_created:
                evidence_id = evidence_created[-1]
                restrictions = state.restrictions
                for restriction in state.restrictions:
                    if (
                        restriction.kind is PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN
                        and restriction.pump_id == process.pump_id
                        and restriction.status is PumpStationRestrictionStatus.ACTIVE
                    ):
                        lifted_restriction = replace(
                            restriction,
                            status=PumpStationRestrictionStatus.LIFTED,
                            evidence_id=evidence_id,
                        )
                        restrictions = replace_restriction(
                            restrictions,
                            lifted_restriction,
                        )
                        restriction_changes = (
                            *restriction_changes,
                            restriction.restriction_id,
                        )
                state = replace(state, restrictions=restrictions)
    return (
        state,
        execution,
        process_changes,
        restriction_changes,
        obligation_changes,
        work_order_changes,
        evidence_created,
        evidence_sources_changed,
        evidence_treatments_changed,
        physical_change,
    )
