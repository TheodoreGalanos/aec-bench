# ABOUTME: Applies the first wastewater pump-station stewardship policy over the physical kernel.
# ABOUTME: Provides deterministic proposals, scheduled events, institutional state, and receipts.

from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass, replace
from decimal import Decimal
from enum import Enum

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    advance_pump_station,
    assess_pump_station,
    transfer_duty_to_standby,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    OperatingInterval,
    PumpStationChangeKind,
    PumpStationEnvironment,
    PumpStationModel,
    PumpStationState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_events import (
    apply_scheduled_event as _apply_scheduled_event,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_events import (
    event_sort_key as _event_sort_key,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_events import (
    new_event as _event,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_events import (
    record_id as _record_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_events import (
    replace_restriction as _replace_restriction,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_events import (
    replace_work_order as _replace_work_order,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_events import (
    schedule_process as _schedule_process,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_events import (
    sorted_events as _sorted_events,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    ContinueOperation,
    PumpStationAuthority,
    PumpStationAuthorityDecision,
    PumpStationAuthorityOutcome,
    PumpStationEventType,
    PumpStationExecutionOutcome,
    PumpStationObligation,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationProcessKind,
    PumpStationProposalError,
    PumpStationRestriction,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    PumpStationSchedule,
    PumpStationScheduledEvent,
    PumpStationStewardshipState,
    PumpStationTransition,
    PumpStationTransitionReceipt,
    PumpStationWorkOrder,
    PumpStationWorkOrderStatus,
    PumpStationWorkResources,
    RequestConditionalDeferral,
    RequestInspection,
    RequestObstructionClearance,
    RequestProvisionalClosure,
    RequestProvisionalReturn,
    RequestVerification,
    TransferDuty,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_policy import (
    PROPOSAL_TYPES as _PROPOSAL_TYPES,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_policy import (
    active_restriction as _active_restriction,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_policy import (
    decide_proposal as _decide_proposal,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_policy import (
    work_order as _work_order,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_policy import (
    work_order_for_pump as _work_order_for_pump,
)


def _canonical_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _canonical_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"unsupported canonical value {type(value).__name__}")


def _state_id(state: PumpStationStewardshipState) -> str:
    payload = json.dumps(
        _canonical_value(state),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _transition_id(sequence: int) -> str:
    return f"transition-{sequence:04d}"


def _finish_transition(
    previous: PumpStationStewardshipState,
    candidate: PumpStationStewardshipState,
    *,
    trigger: str,
    proposal_id: str | None,
    authority: PumpStationAuthorityDecision | None,
    execution: PumpStationExecutionOutcome,
    clock_delta_seconds: int = 0,
    applied_event_types: tuple[PumpStationEventType, ...] = (),
    processes_changed: tuple[str, ...] = (),
    restrictions_changed: tuple[str, ...] = (),
    obligations_changed: tuple[str, ...] = (),
    work_orders_changed: tuple[str, ...] = (),
    evidence_created: tuple[str, ...] = (),
    physical_change: PumpStationChangeKind | None = None,
) -> PumpStationTransition:
    sequence = previous.sequence + 1
    state = replace(candidate, sequence=sequence)
    return PumpStationTransition(
        state=state,
        receipt=PumpStationTransitionReceipt(
            transition_id=_transition_id(sequence),
            sequence=sequence,
            trigger=trigger,
            proposal_id=proposal_id,
            authority=authority,
            execution=execution,
            pre_state_id=_state_id(previous),
            post_state_id=_state_id(state),
            clock_delta_seconds=clock_delta_seconds,
            applied_event_types=applied_event_types,
            processes_changed=processes_changed,
            restrictions_changed=restrictions_changed,
            obligations_changed=obligations_changed,
            work_orders_changed=work_orders_changed,
            evidence_created=evidence_created,
            physical_change=physical_change,
        ),
    )


def _obligation_events(
    model: PumpStationModel,
    obligation: PumpStationObligation,
    sequence: int,
) -> tuple[PumpStationScheduledEvent, ...]:
    prefix = obligation.kind.value
    return (
        _event(
            sequence=sequence,
            suffix=f"{prefix}-due",
            event_type=PumpStationEventType.OBLIGATION_DUE,
            scheduled_seconds=obligation.due_calendar_seconds,
            obligation_id=obligation.obligation_id,
        ),
        _event(
            sequence=sequence,
            suffix=f"{prefix}-overdue",
            event_type=PumpStationEventType.OBLIGATION_OVERDUE,
            scheduled_seconds=obligation.due_calendar_seconds + 1,
            obligation_id=obligation.obligation_id,
        ),
        _event(
            sequence=sequence,
            suffix=f"{prefix}-breach",
            event_type=PumpStationEventType.OBLIGATION_BREACH,
            scheduled_seconds=(obligation.due_calendar_seconds + model.inflow.diagnostic_period_seconds),
            obligation_id=obligation.obligation_id,
        ),
    )


def create_stewardship_state(
    model: PumpStationModel,
    physical: PumpStationState,
    environment: PumpStationEnvironment,
    *,
    schedule: PumpStationSchedule | None = None,
) -> PumpStationStewardshipState:
    """Create the initial in-memory stewardship state over a physical state."""
    assessment = assess_pump_station(
        model,
        physical,
        environment,
    )
    if assessment.state != physical:
        raise PumpStationProposalError(
            "stewardship-state",
            "physical assessment unexpectedly changed state",
        )
    current_schedule = schedule or PumpStationSchedule(
        access_available_after_seconds=model.resources.repair_kit_lead_seconds,
        repair_kit_available_after_seconds=model.resources.repair_kit_lead_seconds,
    )
    now = physical.calendar_seconds
    events = [
        _event(
            sequence=0,
            suffix="access-available",
            event_type=PumpStationEventType.ACCESS_AVAILABLE,
            scheduled_seconds=(now + current_schedule.access_available_after_seconds),
        )
    ]
    if not model.resources.repair_kit_initially_available:
        events.append(
            _event(
                sequence=0,
                suffix="repair-kit-available",
                event_type=PumpStationEventType.REPAIR_KIT_AVAILABLE,
                scheduled_seconds=(now + current_schedule.repair_kit_available_after_seconds),
            )
        )
    if current_schedule.access_withdrawal_after_seconds is not None:
        events.append(
            _event(
                sequence=0,
                suffix="access-withdrawn",
                event_type=PumpStationEventType.ACCESS_WITHDRAWN,
                scheduled_seconds=(now + current_schedule.access_withdrawal_after_seconds),
            )
        )
    return PumpStationStewardshipState(
        physical=physical,
        environment=environment,
        sequence=0,
        resources=PumpStationWorkResources(
            access_window_seconds=0,
            repair_kit_available=model.resources.repair_kit_initially_available,
            available_intervention_slots=(model.resources.concurrent_intervention_limit),
        ),
        restrictions=(),
        obligations=(),
        work_orders=(),
        processes=(),
        evidence=(),
        scheduled_events=_sorted_events(tuple(events)),
    )


def _apply_deferral(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal: RequestConditionalDeferral,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    sequence = state.sequence + 1
    restriction = PumpStationRestriction(
        restriction_id=_record_id("restriction", sequence, "deferred"),
        kind=PumpStationRestrictionKind.DEFERRED_PUMP_NOT_DUTY,
        pump_id=proposal.pump_id,
        status=PumpStationRestrictionStatus.ACTIVE,
        created_sequence=sequence,
    )
    obligation = PumpStationObligation(
        obligation_id=_record_id("obligation", sequence, "deferred-follow-up"),
        kind=PumpStationObligationKind.DEFERRED_FOLLOW_UP,
        pump_id=proposal.pump_id,
        status=PumpStationObligationStatus.ACTIVE,
        originating_proposal_id=proposal.context.proposal_id,
        responsible_authority=PumpStationAuthority.MAINTENANCE,
        linked_restriction_id=restriction.restriction_id,
        due_calendar_seconds=(state.physical.calendar_seconds + model.resources.repair_kit_lead_seconds),
        due_runtime_seconds=(
            state.physical.pump(proposal.pump_id).exposure.runtime_seconds + model.inflow.diagnostic_period_seconds
        ),
        created_sequence=sequence,
    )
    work_order = PumpStationWorkOrder(
        work_order_id=f"work-order-{proposal.pump_id}",
        pump_id=proposal.pump_id,
        status=PumpStationWorkOrderStatus.OPEN,
        created_sequence=sequence,
    )
    candidate = replace(
        state,
        restrictions=(*state.restrictions, restriction),
        obligations=(*state.obligations, obligation),
        work_orders=(*state.work_orders, work_order),
        scheduled_events=_sorted_events(
            (
                *state.scheduled_events,
                *_obligation_events(model, obligation, sequence),
            )
        ),
    )
    return _finish_transition(
        state,
        candidate,
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.COMPLETED,
        restrictions_changed=(restriction.restriction_id,),
        obligations_changed=(obligation.obligation_id,),
        work_orders_changed=(work_order.work_order_id,),
    )


def _apply_transfer(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal: TransferDuty,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    physical = transfer_duty_to_standby(
        model,
        state.physical,
        state.environment,
    )
    return _finish_transition(
        state,
        replace(state, physical=physical.state),
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.COMPLETED,
        physical_change=physical.change_kind,
    )


def _apply_inspection_request(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal: RequestInspection,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    sequence = state.sequence + 1
    work_order = _work_order_for_pump(state, proposal.pump_id)
    candidate = state
    if work_order is None:
        work_order = PumpStationWorkOrder(
            work_order_id=f"work-order-{proposal.pump_id}",
            pump_id=proposal.pump_id,
            status=PumpStationWorkOrderStatus.OPEN,
            created_sequence=sequence,
        )
        candidate = replace(
            candidate,
            work_orders=(*candidate.work_orders, work_order),
        )
    candidate, process = _schedule_process(
        candidate,
        sequence=sequence,
        kind=PumpStationProcessKind.INSPECTION,
        pump_id=proposal.pump_id,
        work_order=work_order,
        duration_seconds=model.inflow.diagnostic_period_seconds,
        performer=PumpStationAuthority.MAINTENANCE,
    )
    return _finish_transition(
        state,
        candidate,
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.SCHEDULED,
        processes_changed=(process.process_id,),
        work_orders_changed=(work_order.work_order_id,),
    )


def _apply_clearance_request(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal: RequestObstructionClearance,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    sequence = state.sequence + 1
    work_order = _work_order_for_pump(state, proposal.pump_id)
    if work_order is None:
        raise PumpStationProposalError(
            "stewardship-state",
            "clearance permission requires a work order",
        )
    candidate, process = _schedule_process(
        state,
        sequence=sequence,
        kind=PumpStationProcessKind.OBSTRUCTION_CLEARANCE,
        pump_id=proposal.pump_id,
        work_order=work_order,
        duration_seconds=model.resources.access_duration_seconds,
        performer=PumpStationAuthority.MAINTENANCE,
        source_evidence_id=proposal.inspection_evidence_id,
    )
    return _finish_transition(
        state,
        candidate,
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.SCHEDULED,
        processes_changed=(process.process_id,),
        work_orders_changed=(work_order.work_order_id,),
    )


def _apply_provisional_return(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal: RequestProvisionalReturn,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    sequence = state.sequence + 1
    deferred = _active_restriction(
        state,
        PumpStationRestrictionKind.DEFERRED_PUMP_NOT_DUTY,
        proposal.pump_id,
    )
    if deferred is None:
        raise PumpStationProposalError(
            "stewardship-state",
            "provisional return requires an active deferred restriction",
        )
    lifted = replace(
        deferred,
        status=PumpStationRestrictionStatus.LIFTED,
        evidence_id=proposal.functional_check_evidence_id,
    )
    run_in = PumpStationRestriction(
        restriction_id=_record_id("restriction", sequence, "run-in"),
        kind=PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN,
        pump_id=proposal.pump_id,
        status=PumpStationRestrictionStatus.ACTIVE,
        created_sequence=sequence,
        evidence_id=proposal.functional_check_evidence_id,
    )
    obligation = PumpStationObligation(
        obligation_id=_record_id("obligation", sequence, "verification"),
        kind=PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
        pump_id=proposal.pump_id,
        status=PumpStationObligationStatus.ACTIVE,
        originating_proposal_id=proposal.context.proposal_id,
        responsible_authority=PumpStationAuthority.VERIFICATION,
        linked_restriction_id=run_in.restriction_id,
        due_calendar_seconds=(state.physical.calendar_seconds + 2 * model.inflow.diagnostic_period_seconds),
        due_runtime_seconds=(
            state.physical.pump(proposal.pump_id).exposure.runtime_seconds + model.inflow.diagnostic_period_seconds
        ),
        created_sequence=sequence,
    )
    restrictions = (
        *_replace_restriction(state.restrictions, lifted),
        run_in,
    )
    candidate = replace(
        state,
        restrictions=restrictions,
        obligations=(*state.obligations, obligation),
        scheduled_events=_sorted_events(
            (
                *state.scheduled_events,
                *_obligation_events(model, obligation, sequence),
            )
        ),
    )
    return _finish_transition(
        state,
        candidate,
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.COMPLETED,
        restrictions_changed=(lifted.restriction_id, run_in.restriction_id),
        obligations_changed=(obligation.obligation_id,),
    )


def _apply_provisional_closure(
    state: PumpStationStewardshipState,
    proposal: RequestProvisionalClosure,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    work_order = _work_order(state, proposal.work_order_id)
    if work_order is None:
        raise PumpStationProposalError(
            "stewardship-state",
            "closure permission requires a work order",
        )
    closed = replace(
        work_order,
        status=PumpStationWorkOrderStatus.PROVISIONALLY_CLOSED,
    )
    return _finish_transition(
        state,
        replace(
            state,
            work_orders=_replace_work_order(state.work_orders, closed),
        ),
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.COMPLETED,
        work_orders_changed=(closed.work_order_id,),
    )


def _apply_verification_request(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal: RequestVerification,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    sequence = state.sequence + 1
    work_order = _work_order_for_pump(state, proposal.pump_id)
    if work_order is None:
        raise PumpStationProposalError(
            "stewardship-state",
            "verification requires a work order",
        )
    candidate, process = _schedule_process(
        state,
        sequence=sequence,
        kind=PumpStationProcessKind.POST_MAINTENANCE_VERIFICATION,
        pump_id=proposal.pump_id,
        work_order=work_order,
        duration_seconds=model.inflow.diagnostic_period_seconds,
        performer=PumpStationAuthority.VERIFICATION,
    )
    candidate = replace(candidate, work_orders=state.work_orders)
    return _finish_transition(
        state,
        candidate,
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.SCHEDULED,
        processes_changed=(process.process_id,),
    )


def apply_stewardship_proposal(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal: object,
) -> PumpStationTransition:
    """Validate, authorise, and apply one closed first-world proposal."""
    if not isinstance(proposal, _PROPOSAL_TYPES):
        raise PumpStationProposalError(
            "proposal-type",
            f"unsupported proposal type {type(proposal).__name__}",
        )
    typed_proposal = proposal
    authority = _decide_proposal(model, state, typed_proposal)
    if authority.outcome in {
        PumpStationAuthorityOutcome.INVALID,
        PumpStationAuthorityOutcome.DENIED,
        PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES,
    }:
        return _finish_transition(
            state,
            state,
            trigger="proposal",
            proposal_id=typed_proposal.context.proposal_id,
            authority=authority,
            execution=PumpStationExecutionOutcome.CANCELLED,
        )
    if isinstance(typed_proposal, ContinueOperation):
        return _advance_to_next_decision_point(
            model,
            state,
            proposal_id=typed_proposal.context.proposal_id,
            authority=authority,
        )
    if isinstance(typed_proposal, RequestConditionalDeferral):
        return _apply_deferral(model, state, typed_proposal, authority)
    if isinstance(typed_proposal, TransferDuty):
        return _apply_transfer(model, state, typed_proposal, authority)
    if isinstance(typed_proposal, RequestInspection):
        return _apply_inspection_request(
            model,
            state,
            typed_proposal,
            authority,
        )
    if isinstance(typed_proposal, RequestObstructionClearance):
        return _apply_clearance_request(
            model,
            state,
            typed_proposal,
            authority,
        )
    if isinstance(typed_proposal, RequestProvisionalReturn):
        return _apply_provisional_return(
            model,
            state,
            typed_proposal,
            authority,
        )
    if isinstance(typed_proposal, RequestProvisionalClosure):
        return _apply_provisional_closure(
            state,
            typed_proposal,
            authority,
        )
    return _apply_verification_request(
        model,
        state,
        typed_proposal,
        authority,
    )


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _advance_to_next_decision_point(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    *,
    proposal_id: str | None,
    authority: PumpStationAuthorityDecision | None,
) -> PumpStationTransition:
    if not state.scheduled_events:
        return _finish_transition(
            state,
            state,
            trigger="quiescent",
            proposal_id=proposal_id,
            authority=authority,
            execution=PumpStationExecutionOutcome.COMPLETED,
        )
    blocked = _active_restriction(
        state,
        PumpStationRestrictionKind.DEFERRED_PUMP_NOT_DUTY,
        state.physical.duty_pump_id,
    )
    if blocked is not None:
        raise PumpStationProposalError(
            "restricted-duty",
            "the deferred duty pump must transfer before time advances",
        )
    scheduled_seconds = state.scheduled_events[0].scheduled_seconds
    if scheduled_seconds < state.physical.calendar_seconds:
        raise PumpStationProposalError(
            "scheduled-event",
            "event schedule moved behind the current calendar",
        )
    events = tuple(event for event in state.scheduled_events if event.scheduled_seconds == scheduled_seconds)
    pending_events = tuple(event for event in state.scheduled_events if event.scheduled_seconds != scheduled_seconds)
    elapsed = scheduled_seconds - state.physical.calendar_seconds
    physical = state.physical
    physical_change: PumpStationChangeKind | None = None
    if elapsed:
        advanced = advance_pump_station(
            model,
            physical,
            OperatingInterval(
                elapsed_seconds=elapsed,
                duty_runtime_seconds=elapsed,
                duty_completed_starts=0,
                environment=state.environment,
            ),
        )
        physical = advanced.state
        physical_change = advanced.change_kind
    candidate = replace(
        state,
        physical=physical,
        scheduled_events=pending_events,
    )
    execution = PumpStationExecutionOutcome.COMPLETED
    process_changes: tuple[str, ...] = ()
    restriction_changes: tuple[str, ...] = ()
    obligation_changes: tuple[str, ...] = ()
    work_order_changes: tuple[str, ...] = ()
    evidence_created: tuple[str, ...] = ()
    applied_event_types: tuple[PumpStationEventType, ...] = ()
    sequence = state.sequence + 1
    for event in sorted(events, key=_event_sort_key):
        (
            candidate,
            event_execution,
            event_processes,
            event_restrictions,
            event_obligations,
            event_work_orders,
            event_evidence,
            event_physical_change,
        ) = _apply_scheduled_event(model, candidate, event, sequence)
        applied_event_types = (*applied_event_types, event.event_type)
        process_changes = (*process_changes, *event_processes)
        restriction_changes = (*restriction_changes, *event_restrictions)
        obligation_changes = (*obligation_changes, *event_obligations)
        work_order_changes = (*work_order_changes, *event_work_orders)
        evidence_created = (*evidence_created, *event_evidence)
        if event_execution in {
            PumpStationExecutionOutcome.INTERRUPTED,
            PumpStationExecutionOutcome.FAILED,
        }:
            execution = event_execution
        if event_physical_change is not None:
            physical_change = event_physical_change
    return _finish_transition(
        state,
        candidate,
        trigger="scheduled-events",
        proposal_id=proposal_id,
        authority=authority,
        execution=execution,
        clock_delta_seconds=elapsed,
        applied_event_types=applied_event_types,
        processes_changed=_unique(process_changes),
        restrictions_changed=_unique(restriction_changes),
        obligations_changed=_unique(obligation_changes),
        work_orders_changed=_unique(work_order_changes),
        evidence_created=_unique(evidence_created),
        physical_change=physical_change,
    )


def advance_to_next_decision_point(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
) -> PumpStationTransition:
    """Advance to and apply the next canonically ordered event group."""
    return _advance_to_next_decision_point(
        model,
        state,
        proposal_id=None,
        authority=None,
    )
