# ABOUTME: Applies the first wastewater pump-station stewardship policy over the physical kernel.
# ABOUTME: Provides deterministic proposals, scheduled events, institutional state, and receipts.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, TypeVar, cast

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PUMP_STATION_EVIDENCE_DELAY_SECONDS,
    PumpStationEvidenceHealth,
    PumpStationEvidenceQuality,
    PumpStationEvidenceTreatment,
    PumpStationEvidenceTreatmentClass,
    PumpStationEvidenceTreatmentRequest,
    PumpStationEvidenceTreatmentStatus,
    PumpStationObservationSource,
    evidence_quality_at,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    advance_pump_station,
    assess_pump_station,
    initial_pump_station_state,
    transfer_duty_to_standby,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    OperatingInterval,
    PumpCondition,
    PumpStationChangeKind,
    PumpStationCoupledModel,
    PumpStationEnvironment,
    PumpStationModel,
    PumpStationState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
    PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
    PumpStationPhysicalTreatmentActivationRequest,
    apply_physical_treatment_effect,
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
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    stewardship_state_id as _state_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_AUTHORITY_POLICY_VERSION,
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V2,
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V3,
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V4,
    PUMP_STATION_COUPLED_TREATMENT_VERSION,
    PUMP_STATION_RECEIPT_VERSION,
    PUMP_STATION_RECEIPT_VERSION_V2,
    PUMP_STATION_RECEIPT_VERSION_V3,
    PUMP_STATION_RECEIPT_VERSION_V4,
    PUMP_STATION_STATE_VERSION_V1,
    PUMP_STATION_STATE_VERSION_V2,
    PUMP_STATION_STATE_VERSION_V3,
    PUMP_STATION_TRANSITION_RULE_VERSION,
    PUMP_STATION_TRANSITION_RULE_VERSION_V2,
    PUMP_STATION_TRANSITION_RULE_VERSION_V3,
    PUMP_STATION_TRANSITION_RULE_VERSION_V4,
    CancelProcess,
    ContinueOperation,
    PumpStationAuthority,
    PumpStationAuthorityDecision,
    PumpStationAuthorityOutcome,
    PumpStationCommonBoundaryRequest,
    PumpStationCoupledStewardshipState,
    PumpStationCoupledTreatmentRequest,
    PumpStationEventType,
    PumpStationEvidence,
    PumpStationEvidenceKind,
    PumpStationExecutionOutcome,
    PumpStationObligation,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationPendingEvidence,
    PumpStationProcess,
    PumpStationProcessKind,
    PumpStationProcessOutcomeRequest,
    PumpStationProcessStatus,
    PumpStationProposal,
    PumpStationProposalError,
    PumpStationRestriction,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    PumpStationRootControl,
    PumpStationSchedule,
    PumpStationScheduledEvent,
    PumpStationStewardshipState,
    PumpStationTransition,
    PumpStationTransitionReceipt,
    PumpStationTransitionReceiptV4,
    PumpStationTransitionV4,
    PumpStationWorkOrder,
    PumpStationWorkOrderStatus,
    PumpStationWorkResources,
    RequestConditionalDeferral,
    RequestConditionCheck,
    RequestDependencyWaiver,
    RequestDutyAssignment,
    RequestFunctionalCheck,
    RequestInspection,
    RequestObstructionClearance,
    RequestProvisionalClosure,
    RequestProvisionalReturn,
    RequestVerification,
    ResumeProcess,
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
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationCoupledActorView,
    PumpStationInformationSet,
    bind_information_set,
    coupled_actor_view_id,
    proposal_binding_error,
)


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
    applied_event_ids: tuple[str, ...] = (),
    applied_event_types: tuple[PumpStationEventType, ...] = (),
    processes_changed: tuple[str, ...] = (),
    restrictions_changed: tuple[str, ...] = (),
    obligations_changed: tuple[str, ...] = (),
    work_orders_changed: tuple[str, ...] = (),
    evidence_created: tuple[str, ...] = (),
    evidence_sources_changed: tuple[str, ...] = (),
    evidence_treatments_changed: tuple[str, ...] = (),
    physical_change: PumpStationChangeKind | None = None,
) -> PumpStationTransition:
    sequence = previous.sequence + 1
    state = replace(candidate, sequence=sequence)
    versions = {
        PUMP_STATION_STATE_VERSION_V1: (
            PUMP_STATION_RECEIPT_VERSION,
            PUMP_STATION_AUTHORITY_POLICY_VERSION,
            PUMP_STATION_TRANSITION_RULE_VERSION,
        ),
        PUMP_STATION_STATE_VERSION_V2: (
            PUMP_STATION_RECEIPT_VERSION_V2,
            PUMP_STATION_AUTHORITY_POLICY_VERSION_V2,
            PUMP_STATION_TRANSITION_RULE_VERSION_V2,
        ),
        PUMP_STATION_STATE_VERSION_V3: (
            PUMP_STATION_RECEIPT_VERSION_V3,
            PUMP_STATION_AUTHORITY_POLICY_VERSION_V3,
            PUMP_STATION_TRANSITION_RULE_VERSION_V3,
        ),
    }[state.state_version]
    return PumpStationTransition(
        state=state,
        receipt=PumpStationTransitionReceipt(
            receipt_version=versions[0],
            authority_policy_version=versions[1],
            transition_rule_version=versions[2],
            transition_id=_transition_id(sequence),
            sequence=sequence,
            trigger=trigger,
            proposal_id=proposal_id,
            authority=authority,
            execution=execution,
            pre_state_id=_state_id(previous),
            post_state_id=_state_id(state),
            clock_delta_seconds=clock_delta_seconds,
            applied_event_ids=applied_event_ids,
            applied_event_types=applied_event_types,
            processes_changed=processes_changed,
            restrictions_changed=restrictions_changed,
            obligations_changed=obligations_changed,
            work_orders_changed=work_orders_changed,
            evidence_created=evidence_created,
            physical_change=physical_change,
            evidence_sources_changed=evidence_sources_changed,
            evidence_treatments_changed=evidence_treatments_changed,
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


def _runtime_due_events(
    state: PumpStationStewardshipState,
) -> tuple[PumpStationScheduledEvent, ...]:
    """Return due events reachable through the current duty-pump runtime."""
    duty_pump = state.physical.pump(state.physical.duty_pump_id)
    now = state.physical.calendar_seconds
    events = tuple(
        _event(
            sequence=obligation.created_sequence,
            suffix=f"{obligation.obligation_id}-runtime-due",
            event_type=PumpStationEventType.OBLIGATION_DUE,
            scheduled_seconds=(
                now
                + max(
                    0,
                    obligation.due_runtime_seconds - duty_pump.exposure.runtime_seconds,
                )
            ),
            obligation_id=obligation.obligation_id,
        )
        for obligation in state.obligations
        if obligation.status is PumpStationObligationStatus.ACTIVE and obligation.pump_id == duty_pump.pump_id
    )
    return _sorted_events(events)


def _runtime_obligation_follow_up_events(
    model: PumpStationModel,
    obligation: PumpStationObligation,
    due_seconds: int,
) -> tuple[PumpStationScheduledEvent, ...]:
    """Schedule overdue and breach events from a runtime-triggered due boundary."""
    return (
        _event(
            sequence=obligation.created_sequence,
            suffix=f"{obligation.obligation_id}-runtime-overdue",
            event_type=PumpStationEventType.OBLIGATION_OVERDUE,
            scheduled_seconds=due_seconds + 1,
            obligation_id=obligation.obligation_id,
        ),
        _event(
            sequence=obligation.created_sequence,
            suffix=f"{obligation.obligation_id}-runtime-breach",
            event_type=PumpStationEventType.OBLIGATION_BREACH,
            scheduled_seconds=due_seconds + model.inflow.diagnostic_period_seconds,
            obligation_id=obligation.obligation_id,
        ),
    )


def _next_event_group(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
) -> (
    tuple[
        int,
        tuple[PumpStationScheduledEvent, ...],
        tuple[PumpStationScheduledEvent, ...],
    ]
    | None
):
    """Select the first calendar or running-pump obligation boundary."""
    runtime_events = _runtime_due_events(state)
    next_calendar = state.scheduled_events[0].scheduled_seconds if state.scheduled_events else None
    next_runtime = runtime_events[0].scheduled_seconds if runtime_events else None
    candidates = tuple(value for value in (next_calendar, next_runtime) if value is not None)
    if not candidates:
        return None
    scheduled_seconds = min(candidates)
    events = tuple(event for event in state.scheduled_events if event.scheduled_seconds == scheduled_seconds)
    pending = tuple(event for event in state.scheduled_events if event.scheduled_seconds != scheduled_seconds)
    calendar_due_ids = {
        event.obligation_id for event in events if event.event_type is PumpStationEventType.OBLIGATION_DUE
    }
    activated_runtime_events = tuple(
        event
        for event in runtime_events
        if event.scheduled_seconds == scheduled_seconds and event.obligation_id not in calendar_due_ids
    )
    for runtime_event in activated_runtime_events:
        obligation = next(item for item in state.obligations if item.obligation_id == runtime_event.obligation_id)
        pending = tuple(event for event in pending if event.obligation_id != obligation.obligation_id)
        pending = _sorted_events(
            (
                *pending,
                *_runtime_obligation_follow_up_events(
                    model,
                    obligation,
                    scheduled_seconds,
                ),
            )
        )
    return (
        scheduled_seconds,
        tuple(sorted((*events, *activated_runtime_events), key=_event_sort_key)),
        pending,
    )


def create_stewardship_state(
    model: PumpStationModel,
    physical: PumpStationState,
    environment: PumpStationEnvironment,
    *,
    schedule: PumpStationSchedule | None = None,
    state_version: str = PUMP_STATION_STATE_VERSION_V1,
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
    if current_schedule.access_restored_after_seconds is not None:
        events.append(
            _event(
                sequence=0,
                suffix="access-restored",
                event_type=PumpStationEventType.ACCESS_AVAILABLE,
                scheduled_seconds=(now + current_schedule.access_restored_after_seconds),
            )
        )
    for index, delay_seconds in enumerate(
        current_schedule.decision_point_after_seconds,
        start=1,
    ):
        events.append(
            _event(
                sequence=0,
                suffix=f"decision-point-{index:02d}",
                event_type=PumpStationEventType.DECISION_POINT,
                scheduled_seconds=(now + delay_seconds),
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
        state_version=state_version,
    )


def create_rich_work_reference_state(
    model: PumpStationModel,
    *,
    schedule: PumpStationSchedule | None = None,
) -> PumpStationStewardshipState:
    """Create the approved overlapping-work reference state from real physics."""
    environment = PumpStationEnvironment(
        inflow_m3_s=model.inflow.assessment_m3_s,
        wet_well_level_m=model.wet_well.start_level_m,
        isolated=False,
    )
    physical = replace(
        initial_pump_station_state(model),
        duty_pump_id="pump-b",
        standby_pump_id="pump-a",
    )
    physical = advance_pump_station(
        model,
        physical,
        OperatingInterval(
            elapsed_seconds=7_200_000,
            duty_runtime_seconds=7_200_000,
            duty_completed_starts=1_000,
            environment=environment,
        ),
    ).state
    current_schedule = schedule or PumpStationSchedule(
        access_available_after_seconds=model.resources.repair_kit_lead_seconds,
        repair_kit_available_after_seconds=model.resources.repair_kit_lead_seconds,
        access_withdrawal_after_seconds=(
            model.resources.repair_kit_lead_seconds + model.inflow.diagnostic_period_seconds // 2
        ),
        access_restored_after_seconds=(
            model.resources.repair_kit_lead_seconds
            + model.inflow.diagnostic_period_seconds // 2
            + model.resources.access_duration_seconds
        ),
    )
    base = create_stewardship_state(
        model,
        physical,
        environment,
        schedule=current_schedule,
        state_version=PUMP_STATION_STATE_VERSION_V2,
    )
    work_order_a = PumpStationWorkOrder(
        work_order_id="work-order-pump-a",
        pump_id="pump-a",
        status=PumpStationWorkOrderStatus.SCOPE_COMPLETED,
        created_sequence=0,
    )
    work_order_b = PumpStationWorkOrder(
        work_order_id="work-order-pump-b",
        pump_id="pump-b",
        status=PumpStationWorkOrderStatus.OPEN,
        created_sequence=0,
    )
    resource_order = PumpStationWorkOrder(
        work_order_id="work-order-site-resources",
        pump_id="site",
        status=PumpStationWorkOrderStatus.IN_PROGRESS,
        created_sequence=0,
    )
    pump_a_limit = PumpStationRestriction(
        restriction_id="restriction-0000-pump-a-run-in",
        kind=PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN,
        pump_id="pump-a",
        status=PumpStationRestrictionStatus.ACTIVE,
        created_sequence=0,
        evidence_id="evidence-0000-functional-checks-pump-a",
    )
    pump_b_limit = PumpStationRestriction(
        restriction_id="restriction-0000-pump-b-work",
        kind=PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN,
        pump_id="pump-b",
        status=PumpStationRestrictionStatus.ACTIVE,
        created_sequence=0,
    )
    verification = PumpStationObligation(
        obligation_id="obligation-0000-pump-a-verification",
        kind=PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
        pump_id="pump-a",
        status=PumpStationObligationStatus.ACTIVE,
        originating_proposal_id="scenario-entry",
        responsible_authority=PumpStationAuthority.VERIFICATION,
        linked_restriction_id=pump_a_limit.restriction_id,
        due_calendar_seconds=(physical.calendar_seconds + 10 * model.inflow.diagnostic_period_seconds),
        due_runtime_seconds=(
            physical.pump("pump-a").exposure.runtime_seconds + 10 * model.inflow.diagnostic_period_seconds
        ),
        created_sequence=0,
    )
    accepted_checks = PumpStationEvidence(
        evidence_id="evidence-0000-functional-checks-pump-a",
        kind=PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
        pump_id="pump-a",
        created_at_seconds=physical.calendar_seconds,
        produced_by=PumpStationAuthority.MAINTENANCE,
        accepted_by=PumpStationAuthority.VERIFICATION,
        passed=True,
    )
    processes: list[PumpStationProcess] = []
    events: list[PumpStationScheduledEvent] = []
    for event in base.scheduled_events:
        if event.event_type is PumpStationEventType.ACCESS_AVAILABLE and event.event_id.endswith("access-available"):
            process = PumpStationProcess(
                process_id="process-0000-access-preparation",
                kind=PumpStationProcessKind.ACCESS_PREPARATION,
                pump_id="site",
                work_order_id=resource_order.work_order_id,
                status=PumpStationProcessStatus.ACTIVE,
                started_at_seconds=physical.calendar_seconds,
                completion_at_seconds=event.scheduled_seconds,
                performer=PumpStationAuthority.WORK_MANAGEMENT,
                remaining_duration_seconds=(event.scheduled_seconds - physical.calendar_seconds),
            )
            processes.append(process)
            events.append(replace(event, process_id=process.process_id))
        elif event.event_type is PumpStationEventType.REPAIR_KIT_AVAILABLE:
            process = PumpStationProcess(
                process_id="process-0000-repair-kit-delivery",
                kind=PumpStationProcessKind.REPAIR_KIT_DELIVERY,
                pump_id="site",
                work_order_id=resource_order.work_order_id,
                status=PumpStationProcessStatus.ACTIVE,
                started_at_seconds=physical.calendar_seconds,
                completion_at_seconds=event.scheduled_seconds,
                performer=PumpStationAuthority.WORK_MANAGEMENT,
                remaining_duration_seconds=(event.scheduled_seconds - physical.calendar_seconds),
            )
            processes.append(process)
            events.append(replace(event, process_id=process.process_id))
        else:
            events.append(event)
    events.extend(_obligation_events(model, verification, 0))
    return replace(
        base,
        restrictions=(pump_a_limit, pump_b_limit),
        obligations=(verification,),
        work_orders=(work_order_a, work_order_b, resource_order),
        processes=tuple(processes),
        evidence=(accepted_checks,),
        scheduled_events=_sorted_events(tuple(events)),
    )


def materialize_evidence_health_state(
    model: PumpStationModel,
    base: PumpStationStewardshipState,
) -> PumpStationStewardshipState:
    """Materialize one complete version 3 state from a version 2 state."""
    if base.state_version != PUMP_STATION_STATE_VERSION_V2:
        raise PumpStationProposalError(
            "evidence-health-source-version",
            "evidence health requires a version 2 source state",
        )
    now = base.physical.calendar_seconds
    assessment = assess_pump_station(model, base.physical, base.environment)
    source = PumpStationObservationSource(
        source_id="station-condition-sensor",
        component_scope=("pump-a", "pump-b"),
        baseline_id="station-condition-baseline.v1",
        operating_regime_id=(f"{base.physical.duty_pump_id}-duty-{base.physical.standby_pump_id}-standby.v1"),
        observation=assessment.observation,
        observed_at_seconds=now,
        produced_at_seconds=now,
        available_at_seconds=now,
        quality=PumpStationEvidenceQuality.CURRENT,
    )
    evidence = tuple(
        replace(
            item,
            health=PumpStationEvidenceHealth(
                observed_at_seconds=item.created_at_seconds,
                produced_at_seconds=item.created_at_seconds,
                available_at_seconds=item.created_at_seconds,
                source_id="maintenance-functional-checks",
                component_scope=(item.pump_id,),
                baseline_id=f"{item.pump_id}-post-maintenance-baseline.v1",
                operating_regime_id=f"{item.pump_id}-standby.v1",
                accepted=item.accepted_by is not None,
                quality=PumpStationEvidenceQuality.CURRENT,
            ),
        )
        for item in base.evidence
    )
    return replace(
        base,
        state_version=PUMP_STATION_STATE_VERSION_V3,
        evidence=evidence,
        evidence_sources=(source,),
        evidence_treatments=(),
        pending_evidence=(),
    )


def create_evidence_health_reference_state(
    model: PumpStationModel,
    *,
    schedule: PumpStationSchedule | None = None,
) -> PumpStationStewardshipState:
    """Create the version 3 reference state with one governed sensor source."""
    current_schedule = schedule or PumpStationSchedule(
        access_available_after_seconds=model.resources.repair_kit_lead_seconds,
        repair_kit_available_after_seconds=model.resources.repair_kit_lead_seconds,
        access_withdrawal_after_seconds=(
            model.resources.repair_kit_lead_seconds + model.inflow.diagnostic_period_seconds // 2
        ),
        access_restored_after_seconds=(
            model.resources.repair_kit_lead_seconds
            + model.inflow.diagnostic_period_seconds // 2
            + model.resources.access_duration_seconds
        ),
        decision_point_after_seconds=(model.inflow.diagnostic_period_seconds,),
    )
    return materialize_evidence_health_state(
        model,
        create_rich_work_reference_state(model, schedule=current_schedule),
    )


def apply_evidence_treatment_schedule(
    state: PumpStationStewardshipState,
    request: PumpStationEvidenceTreatmentRequest,
) -> PumpStationTransition:
    """Schedule one exact version 3 treatment without advancing the clock."""
    if state.state_version != PUMP_STATION_STATE_VERSION_V3:
        raise PumpStationProposalError(
            "evidence-treatment",
            "treatments require a version 3 state",
        )
    if request.based_on_sequence != state.sequence or request.base_state_id != _state_id(state):
        raise PumpStationProposalError(
            "evidence-treatment-binding",
            "treatment request is not bound to the selected state",
        )
    if any(item.treatment_id == request.request_id for item in state.evidence_treatments):
        raise PumpStationProposalError(
            "evidence-treatment-id",
            f"treatment {request.request_id} already exists",
        )
    if not any(item.source_id == request.target_source_id for item in state.evidence_sources):
        raise PumpStationProposalError(
            "evidence-treatment-source",
            request.target_source_id,
        )
    decision_points = tuple(
        event.scheduled_seconds
        for event in state.scheduled_events
        if event.event_type is PumpStationEventType.DECISION_POINT
        and event.scheduled_seconds >= state.physical.calendar_seconds
    )
    if not decision_points:
        raise PumpStationProposalError(
            "evidence-treatment-decision-point",
            "no future decision point is available",
        )
    next_decision_point = min(decision_points)
    if request.effective_decision_point_seconds != next_decision_point:
        raise PumpStationProposalError(
            "evidence-treatment-decision-point",
            "treatment must use the next declared decision point",
        )
    sequence = state.sequence + 1
    treatment = PumpStationEvidenceTreatment(
        treatment_id=request.request_id,
        request=request,
        status=PumpStationEvidenceTreatmentStatus.SCHEDULED,
        scheduled_sequence=sequence,
    )
    activation = _event(
        sequence=sequence,
        suffix=f"{request.treatment_class.value}-activation",
        event_type=PumpStationEventType.EVIDENCE_TREATMENT_ACTIVATION,
        scheduled_seconds=next_decision_point,
        treatment_id=treatment.treatment_id,
    )
    candidate = replace(
        state,
        evidence_treatments=(*state.evidence_treatments, treatment),
        scheduled_events=_sorted_events((*state.scheduled_events, activation)),
    )
    return _finish_transition(
        state,
        candidate,
        trigger="host-control:evidence-treatment-schedule",
        proposal_id=None,
        authority=None,
        execution=PumpStationExecutionOutcome.SCHEDULED,
        evidence_treatments_changed=(treatment.treatment_id,),
    )


def apply_physical_treatment_activation(
    state: PumpStationStewardshipState,
    request: PumpStationPhysicalTreatmentActivationRequest,
) -> PumpStationTransition:
    """Realise one private governed treatment at its declared child clock."""

    if (
        request.treatment_version != PUMP_STATION_PHYSICAL_TREATMENT_VERSION
        or request.visibility_policy != PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY
        or request.decision_right_id != PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT
    ):
        raise PumpStationProposalError(
            "physical-treatment-policy",
            "treatment version, visibility, or decision right is unsupported",
        )
    if request.based_on_sequence != state.sequence or request.base_state_id != _state_id(state):
        raise PumpStationProposalError(
            "physical-treatment-binding",
            "activation request is not bound to the selected child state",
        )
    if state.physical.calendar_seconds < request.activation_calendar_seconds:
        raise PumpStationProposalError(
            "physical-treatment-clock",
            "the child has not reached the declared activation clock",
        )
    available_pumps = {pump.pump_id for pump in state.physical.pumps}
    if not request.affected_pump_ids or not set(request.affected_pump_ids) <= available_pumps:
        raise PumpStationProposalError(
            "physical-treatment-scope",
            "affected pumps are not present in the child state",
        )
    candidate, change = apply_physical_treatment_effect(state, request)
    return _finish_transition(
        state,
        candidate,
        trigger="host-control:physical-treatment-activation",
        proposal_id=None,
        authority=None,
        execution=PumpStationExecutionOutcome.COMPLETED,
        physical_change=change,
    )


def _schedule_work_process(
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
    if state.state_version in {
        PUMP_STATION_STATE_VERSION_V2,
        PUMP_STATION_STATE_VERSION_V3,
    }:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rich_work_processes import (
            schedule_rich_process,
        )

        return schedule_rich_process(
            state,
            sequence=sequence,
            kind=kind,
            pump_id=pump_id,
            work_order=work_order,
            duration_seconds=duration_seconds,
            performer=performer,
            source_evidence_id=source_evidence_id,
        )
    return _schedule_process(
        state,
        sequence=sequence,
        kind=kind,
        pump_id=pump_id,
        work_order=work_order,
        duration_seconds=duration_seconds,
        performer=performer,
        source_evidence_id=source_evidence_id,
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
    candidate, process = _schedule_work_process(
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


def _apply_condition_check(
    state: PumpStationStewardshipState,
    proposal: RequestConditionCheck,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    if len(state.evidence_sources) != 1:
        raise PumpStationProposalError(
            "evidence-source",
            "condition check requires exactly one governed observation source",
        )
    source = state.evidence_sources[0]
    now = state.physical.calendar_seconds
    quality = evidence_quality_at(
        source.quality,
        observed_at_seconds=source.observed_at_seconds,
        now_seconds=now,
    )
    available = source.reading_available
    superseded = next(
        (
            item
            for item in reversed(state.evidence)
            if item.kind is PumpStationEvidenceKind.CONDITION_CHECK
            and item.pump_id == proposal.pump_id
            and item.health is not None
            and item.health.source_id == source.source_id
            and item.health.accepted
        ),
        None,
    )
    evidence = PumpStationEvidence(
        evidence_id=_record_id(
            "evidence",
            state.sequence + 1,
            "condition-check",
        ),
        kind=PumpStationEvidenceKind.CONDITION_CHECK,
        pump_id=proposal.pump_id,
        created_at_seconds=now,
        produced_by=PumpStationAuthority.OPERATIONS,
        accepted_by=(PumpStationAuthority.OPERATIONS if available else None),
        passed=(source.observation.active_pump_flow_m3_s > 0 if available else None),
        health=PumpStationEvidenceHealth(
            observed_at_seconds=source.observed_at_seconds,
            produced_at_seconds=now,
            available_at_seconds=now,
            source_id=source.source_id,
            component_scope=(proposal.pump_id,),
            baseline_id=source.baseline_id,
            operating_regime_id=source.operating_regime_id,
            accepted=available,
            quality=quality,
            supersedes_evidence_id=(superseded.evidence_id if superseded is not None else None),
        ),
        condition_observation=(source.observation if available else None),
    )
    evidence_health = evidence.health
    if evidence_health is None:
        raise PumpStationProposalError(
            "evidence-health",
            "condition-check evidence lacks health metadata",
        )
    matching_treatments = tuple(
        item
        for item in state.evidence_treatments
        if item.status is PumpStationEvidenceTreatmentStatus.ACTIVE
        and item.request.target_source_id == source.source_id
    )
    delay = next(
        (
            item
            for item in matching_treatments
            if item.request.treatment_class is PumpStationEvidenceTreatmentClass.EVIDENCE_DELAY
        ),
        None,
    )
    contradiction = next(
        (
            item
            for item in matching_treatments
            if item.request.treatment_class is PumpStationEvidenceTreatmentClass.CONTRADICTORY_REPORT
        ),
        None,
    )
    treatments = state.evidence_treatments
    changed_treatments: tuple[str, ...] = ()
    if delay is not None:
        release_at_seconds = now + PUMP_STATION_EVIDENCE_DELAY_SECONDS
        delayed = replace(
            evidence,
            health=replace(
                evidence_health,
                available_at_seconds=release_at_seconds,
            ),
        )
        pending = PumpStationPendingEvidence(
            evidence=delayed,
            treatment_id=delay.treatment_id,
            release_at_seconds=release_at_seconds,
        )
        release = _event(
            sequence=state.sequence + 1,
            suffix="condition-check-release",
            event_type=PumpStationEventType.EVIDENCE_RELEASE,
            scheduled_seconds=release_at_seconds,
            treatment_id=delay.treatment_id,
            evidence_id=evidence.evidence_id,
        )
        applied_delay = replace(
            delay,
            status=PumpStationEvidenceTreatmentStatus.APPLIED,
        )
        treatments = tuple(applied_delay if item.treatment_id == delay.treatment_id else item for item in treatments)
        changed_treatments = (delay.treatment_id,)
        candidate = replace(
            state,
            evidence_treatments=treatments,
            pending_evidence=(*state.pending_evidence, pending),
            scheduled_events=_sorted_events((*state.scheduled_events, release)),
        )
        evidence_created: tuple[str, ...] = ()
    else:
        visible_evidence: tuple[PumpStationEvidence, ...] = (evidence,)
        if contradiction is not None:
            contradictory = replace(
                evidence,
                evidence_id=f"{evidence.evidence_id}-contradictory-report",
                accepted_by=None,
                passed=(not evidence.passed if evidence.passed is not None else False),
                health=replace(
                    evidence_health,
                    accepted=False,
                    quality=PumpStationEvidenceQuality.SUSPECT,
                    contradicts_evidence_id=evidence.evidence_id,
                ),
            )
            visible_evidence = (evidence, contradictory)
            applied_contradiction = replace(
                contradiction,
                status=PumpStationEvidenceTreatmentStatus.APPLIED,
            )
            treatments = tuple(
                applied_contradiction if item.treatment_id == contradiction.treatment_id else item
                for item in treatments
            )
            changed_treatments = (contradiction.treatment_id,)
        candidate = replace(
            state,
            evidence=(*state.evidence, *visible_evidence),
            evidence_treatments=treatments,
        )
        evidence_created = tuple(item.evidence_id for item in visible_evidence)
    return _finish_transition(
        state,
        candidate,
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.COMPLETED,
        evidence_created=evidence_created,
        evidence_treatments_changed=changed_treatments,
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
    candidate, process = _schedule_work_process(
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
    candidate, process = _schedule_work_process(
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


def _apply_resume_process(
    state: PumpStationStewardshipState,
    proposal: ResumeProcess,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rich_work_processes import (
        resume_process,
    )

    resumed = resume_process(
        state,
        proposal.process_id,
        state.sequence + 1,
    )
    if resumed is None:
        return _finish_transition(
            state,
            state,
            trigger="proposal",
            proposal_id=proposal.context.proposal_id,
            authority=PumpStationAuthorityDecision(
                outcome=PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES,
                required_authorities=authority.required_authorities,
                detail="one or more fixed dependencies or resources are unavailable",
            ),
            execution=PumpStationExecutionOutcome.CANCELLED,
        )
    candidate, process = resumed
    return _finish_transition(
        state,
        candidate,
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.IN_PROGRESS,
        processes_changed=(process.process_id,),
        work_orders_changed=(process.work_order_id,),
    )


def _apply_cancel_process(
    state: PumpStationStewardshipState,
    proposal: CancelProcess,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rich_work_processes import (
        cancel_process,
    )

    candidate, process = cancel_process(state, proposal.process_id)
    return _finish_transition(
        state,
        candidate,
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.CANCELLED,
        processes_changed=(process.process_id,),
    )


def _apply_dependency_waiver(
    state: PumpStationStewardshipState,
    proposal: RequestDependencyWaiver,
    authority: PumpStationAuthorityDecision,
) -> PumpStationTransition:
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rich_work_processes import (
        apply_dependency_waiver,
    )

    candidate, _ = apply_dependency_waiver(
        state,
        process_id=proposal.process_id,
        dependency_id=proposal.dependency_id,
        evidence_id=proposal.evidence_id,
        sequence=state.sequence + 1,
    )
    return _finish_transition(
        state,
        candidate,
        trigger="proposal",
        proposal_id=proposal.context.proposal_id,
        authority=authority,
        execution=PumpStationExecutionOutcome.COMPLETED,
        processes_changed=(proposal.process_id,),
    )


def apply_stewardship_proposal(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal: object,
    *,
    information_set: PumpStationInformationSet,
) -> PumpStationTransition:
    """Validate a bound information set, authorise, and apply one proposal."""
    if not isinstance(proposal, _PROPOSAL_TYPES):
        raise PumpStationProposalError(
            "proposal-type",
            f"unsupported proposal type {type(proposal).__name__}",
        )
    typed_proposal = proposal
    binding_error = proposal_binding_error(
        model,
        state,
        typed_proposal.context,
        information_set,
    )
    if binding_error is not None:
        return _finish_transition(
            state,
            state,
            trigger="proposal",
            proposal_id=typed_proposal.context.proposal_id,
            authority=PumpStationAuthorityDecision(
                outcome=PumpStationAuthorityOutcome.INVALID,
                required_authorities=(),
                detail=binding_error,
            ),
            execution=PumpStationExecutionOutcome.CANCELLED,
        )
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
    if isinstance(typed_proposal, RequestConditionCheck):
        return _apply_condition_check(
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
    if isinstance(typed_proposal, ResumeProcess):
        return _apply_resume_process(state, typed_proposal, authority)
    if isinstance(typed_proposal, CancelProcess):
        return _apply_cancel_process(state, typed_proposal, authority)
    if isinstance(typed_proposal, RequestDependencyWaiver):
        return _apply_dependency_waiver(state, typed_proposal, authority)
    return _apply_verification_request(
        model,
        state,
        typed_proposal,
        authority,
    )


def apply_stewardship_proposal_v4(
    model: PumpStationCoupledModel,
    state: PumpStationCoupledStewardshipState,
    proposal: object,
    *,
    information_set: PumpStationInformationSet,
) -> PumpStationTransitionV4:
    """Apply one typed V4 proposal through the task-owned transition rules."""
    view = information_set.base_view
    context = getattr(proposal, "context", None)
    if not isinstance(view, PumpStationCoupledActorView) or context is None:
        raise PumpStationProposalError(
            "proposal-type",
            "V4 proposal requires a V4 actor view and typed context",
        )
    if view.view_id != coupled_actor_view_id(view):
        raise PumpStationProposalError(
            "proposal-binding",
            "V4 actor view identity differs from its complete content",
        )
    if (
        bind_information_set(
            view,
            information_set.observation_history,
            information_set.current_context,
        )
        != information_set
    ):
        raise PumpStationProposalError(
            "proposal-binding",
            "V4 information set identity differs from its content",
        )
    expected = (
        context.agent_tenure_id,
        context.based_on_sequence,
        context.base_view_id,
        context.information_set_id,
    )
    observed = (
        view.agent_tenure_id,
        state.sequence,
        view.view_id,
        information_set.information_set_id,
    )
    if expected != observed or view.state_id != state.state_id or view.sequence != state.sequence:
        raise PumpStationProposalError(
            "proposal-binding",
            "V4 proposal does not bind the selected state and information set",
        )
    action_name, arguments = _v4_proposal_arguments(proposal)
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
        apply_coupled_actor_action,
    )

    return apply_coupled_actor_action(
        state,
        request_id=context.proposal_id,
        action_name=action_name,
        arguments={"reason": context.reason, **arguments},
        model=model,
    )


def validate_legacy_proposal_profile(proposal: PumpStationProposal) -> None:
    """Reject V4-only proposal bindings before legacy serialization can lose them."""
    if (
        isinstance(
            proposal,
            RequestInspection | RequestObstructionClearance | RequestVerification,
        )
        and proposal.backlog_item_id is not None
    ):
        raise PumpStationProposalError(
            "proposal-profile",
            "V4 backlog binding cannot enter a V1-V3 proposal record",
        )


def _v4_proposal_arguments(proposal: object) -> tuple[str, dict[str, object]]:
    """Return the closed V2 actor operation and exact typed proposal fields."""
    if isinstance(proposal, ContinueOperation):
        return "continue_operation", {}
    if isinstance(proposal, RequestDutyAssignment):
        return (
            "request_duty_assignment",
            {
                "ordered_pump_ids": proposal.ordered_pump_ids,
                "source_outage_id": proposal.source_outage_id,
                "source_backlog_item_id": proposal.source_backlog_item_id,
            },
        )
    if isinstance(proposal, RequestInspection):
        if proposal.backlog_item_id is None:
            raise PumpStationProposalError("proposal-binding", "inspection lacks backlog binding")
        return (
            "request_inspection",
            {"pump_id": proposal.pump_id, "backlog_item_id": proposal.backlog_item_id},
        )
    if isinstance(proposal, RequestObstructionClearance):
        if proposal.backlog_item_id is None:
            raise PumpStationProposalError("proposal-binding", "clearance lacks backlog binding")
        return (
            "request_obstruction_clearance",
            {
                "pump_id": proposal.pump_id,
                "backlog_item_id": proposal.backlog_item_id,
                "inspection_evidence_id": proposal.inspection_evidence_id,
            },
        )
    if isinstance(proposal, RequestFunctionalCheck):
        return (
            "request_functional_check",
            {"pump_id": proposal.pump_id, "backlog_item_id": proposal.backlog_item_id},
        )
    if isinstance(proposal, RequestProvisionalReturn):
        return (
            "request_provisional_return",
            {
                "pump_id": proposal.pump_id,
                "functional_check_evidence_id": proposal.functional_check_evidence_id,
            },
        )
    if isinstance(proposal, RequestProvisionalClosure):
        return "request_provisional_closure", {"work_order_id": proposal.work_order_id}
    if isinstance(proposal, RequestVerification):
        if proposal.backlog_item_id is None:
            raise PumpStationProposalError("proposal-binding", "verification lacks backlog binding")
        return (
            "request_post_maintenance_verification",
            {"pump_id": proposal.pump_id, "backlog_item_id": proposal.backlog_item_id},
        )
    if isinstance(proposal, ResumeProcess):
        return "resume_process", {"process_id": proposal.process_id}
    if isinstance(proposal, CancelProcess):
        return "cancel_process", {"process_id": proposal.process_id}
    if isinstance(proposal, RequestConditionCheck):
        return "request_condition_check", {"pump_id": proposal.pump_id}
    if isinstance(proposal, RequestDependencyWaiver):
        return (
            "request_dependency_waiver",
            {
                "process_id": proposal.process_id,
                "dependency_id": proposal.dependency_id,
                "evidence_id": proposal.evidence_id,
            },
        )
    raise PumpStationProposalError(
        "proposal-type",
        f"unsupported V4 proposal type {type(proposal).__name__}",
    )


_CoupledRecordT = TypeVar("_CoupledRecordT")


def _changed_coupled_owner_ids(
    before: tuple[_CoupledRecordT, ...],
    after: tuple[_CoupledRecordT, ...],
    identity: Callable[[_CoupledRecordT], str],
) -> tuple[str, ...]:
    before_by_id = {identity(item): item for item in before}
    after_by_id = {identity(item): item for item in after}
    return tuple(
        sorted(
            record_id
            for record_id in before_by_id.keys() | after_by_id.keys()
            if before_by_id.get(record_id) != after_by_id.get(record_id)
        )
    )


def _coupled_liability_owner_records(
    state: PumpStationCoupledStewardshipState,
) -> dict[str, object]:
    owners: dict[str, object] = {item.obligation_id: item for item in state.obligations}
    owners.update({item.episode_id: item for item in state.outage_episodes})
    owners.update({item.item_id: item for item in state.backlog if item.generation_rule_id in {"WG-06", "WG-07"}})
    return owners


def _changed_coupled_liability_owner_ids(
    before: PumpStationCoupledStewardshipState,
    after: PumpStationCoupledStewardshipState,
) -> tuple[str, ...]:
    before_owners = _coupled_liability_owner_records(before)
    after_owners = _coupled_liability_owner_records(after)
    return tuple(
        sorted(
            owner_id
            for owner_id in before_owners.keys() | after_owners.keys()
            if before_owners.get(owner_id) != after_owners.get(owner_id)
        )
    )


def _required_coupled_authorities(action_kind: str) -> tuple[str, ...]:
    if action_kind == "request_functional_check":
        return ("maintenance", "operations")
    if action_kind in {
        "continue_operation",
        "request_duty_assignment",
        "request_provisional_return",
        "operations_boundary_review",
        "common_boundary_control",
    }:
        return ("operations",)
    if action_kind in {
        "request_inspection",
        "request_obstruction_clearance",
        "resume_process",
        "cancel_process",
    }:
        return ("maintenance",)
    if action_kind in {"request_post_maintenance_verification", "process_outcome"}:
        return ("verification",)
    if action_kind in {"request_provisional_closure", "request_dependency_waiver"}:
        return ("work_management",)
    if action_kind == "request_condition_check":
        return ("engineering",)
    return ("host",)


def finish_coupled_transition(
    before: PumpStationCoupledStewardshipState,
    after: PumpStationCoupledStewardshipState,
    *,
    request_id: str,
    action_kind: str,
    actor_action: bool,
    target_id: str | None,
    backlog_item_id: str | None,
    reason: str,
    changed_record_ids: tuple[str, ...],
    operating_interval_id: str | None = None,
    authority_requirements: tuple[str, ...] | None = None,
) -> PumpStationTransitionV4:
    """Finish one V4 transition with the shared task-owned receipt rules."""
    sequenced = replace(after, sequence=before.sequence + 1)
    receipt = PumpStationTransitionReceiptV4(
        receipt_version=PUMP_STATION_RECEIPT_VERSION_V4,
        authority_policy_version=PUMP_STATION_AUTHORITY_POLICY_VERSION_V4,
        transition_rule_version=PUMP_STATION_TRANSITION_RULE_VERSION_V4,
        sequence=sequenced.sequence,
        transition_id=f"transition-{sequenced.sequence}-{request_id}",
        request_id=request_id,
        action_or_control_kind=action_kind,
        actor_action=actor_action,
        authority_outcome="permitted",
        required_authorities=authority_requirements or _required_coupled_authorities(action_kind),
        authority_decision_detail="All required task authorities accepted the bound request.",
        permit_ids=(f"controlled-test-permit-{request_id}",) if action_kind == "request_functional_check" else (),
        execution_status="applied",
        before_state_id=before.state_id,
        after_state_id=sequenced.state_id,
        start_calendar_seconds=before.calendar_seconds,
        end_calendar_seconds=sequenced.calendar_seconds,
        target_id=target_id,
        backlog_item_id=backlog_item_id,
        reason=reason,
        changed_record_ids=changed_record_ids,
        changed_pool_ids=_changed_coupled_owner_ids(
            before.resources.pools,
            sequenced.resources.pools,
            lambda item: item.pool_id,
        ),
        changed_reservation_ids=_changed_coupled_owner_ids(
            before.resource_reservations,
            sequenced.resource_reservations,
            lambda item: item.reservation_id,
        ),
        changed_backlog_item_ids=_changed_coupled_owner_ids(
            before.backlog,
            sequenced.backlog,
            lambda item: item.item_id,
        ),
        generation_record_ids=_changed_coupled_owner_ids(
            before.generation_records,
            sequenced.generation_records,
            lambda item: item.backlog_item_id,
        ),
        changed_liability_owner_ids=_changed_coupled_liability_owner_ids(
            before,
            sequenced,
        ),
        operating_interval_id=operating_interval_id,
    )
    return PumpStationTransitionV4(state=sequenced, receipt=receipt)


def apply_stewardship_control_v4(
    state: PumpStationCoupledStewardshipState,
    control: PumpStationRootControl,
) -> PumpStationTransitionV4:
    """Apply one closed root host control through the task-owned V4 rules."""
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
        apply_common_boundary_control,
        apply_operations_boundary_review,
        apply_process_outcome,
    )

    if isinstance(control, PumpStationOperationsBoundaryReviewRequest):
        return apply_operations_boundary_review(state, control)
    if isinstance(control, PumpStationProcessOutcomeRequest):
        return apply_process_outcome(state, control)
    if isinstance(control, PumpStationCommonBoundaryRequest):
        return apply_common_boundary_control(state, control)
    if isinstance(control, PumpStationCoupledTreatmentRequest):
        return apply_coupled_treatment(state, control)
    raise PumpStationProposalError(
        "control-type",
        f"unsupported V4 control type {type(control).__name__}",
    )


def apply_coupled_treatment(
    state: PumpStationCoupledStewardshipState,
    request: PumpStationCoupledTreatmentRequest,
) -> PumpStationTransitionV4:
    """Apply one private physical treatment to selected pumps in one child."""
    if request.version != PUMP_STATION_COUPLED_TREATMENT_VERSION:
        raise PumpStationProposalError("coupled-treatment-version", request.version)
    if request.authority_id != "rollout-host":
        raise PumpStationProposalError("coupled-treatment-authority", request.authority_id)
    if request.base_state_id != state.state_id:
        raise PumpStationProposalError("stale-coupled-treatment", request.request_id)
    if not request.treatment_label.strip():
        raise PumpStationProposalError("coupled-treatment-label", request.request_id)
    pump_ids = tuple(pump.pump_id for pump in state.physical.pumps)
    if (
        not request.affected_pump_ids
        or len(set(request.affected_pump_ids)) != len(request.affected_pump_ids)
        or not set(request.affected_pump_ids) <= set(pump_ids)
    ):
        raise PumpStationProposalError("coupled-treatment-targets", request.request_id)
    if request.obstruction_delta < 0 or request.clearance_loss_delta < 0:
        raise PumpStationProposalError("coupled-treatment-delta", request.request_id)
    updated_pumps: list[Any] = []
    for pump in state.physical.pumps:
        if pump.pump_id not in request.affected_pump_ids:
            updated_pumps.append(pump)
            continue
        obstruction = pump.condition.obstruction + request.obstruction_delta
        clearance_loss = pump.condition.clearance_loss + request.clearance_loss_delta
        if obstruction > 1 or clearance_loss > 1:
            raise PumpStationProposalError("coupled-treatment-range", pump.pump_id)
        updated_pumps.append(
            replace(
                pump,
                condition=PumpCondition(
                    obstruction=obstruction,
                    clearance_loss=clearance_loss,
                ),
            )
        )
    updated = replace(
        state,
        physical=replace(
            state.physical,
            pumps=cast(tuple[Any, Any, Any], tuple(updated_pumps)),
        ),
        event_effect_ids=(*state.event_effect_ids, request.content_id),
    )
    return finish_coupled_transition(
        state,
        updated,
        request_id=request.request_id,
        action_kind="coupled_physical_treatment",
        actor_action=False,
        target_id=None,
        backlog_item_id=None,
        reason="Apply the authorised child-only common-cause treatment.",
        changed_record_ids=(request.content_id, *request.affected_pump_ids),
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
    event_group = _next_event_group(model, state)
    if event_group is None:
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
    scheduled_seconds, events, pending_events = event_group
    if scheduled_seconds < state.physical.calendar_seconds:
        raise PumpStationProposalError(
            "scheduled-event",
            "event schedule moved behind the current calendar",
        )
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
    evidence_sources_changed: tuple[str, ...] = ()
    evidence_treatments_changed: tuple[str, ...] = ()
    applied_event_ids: tuple[str, ...] = ()
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
            event_sources,
            event_treatments,
            event_physical_change,
        ) = _apply_scheduled_event(model, candidate, event, sequence)
        applied_event_ids = (*applied_event_ids, event.event_id)
        applied_event_types = (*applied_event_types, event.event_type)
        process_changes = (*process_changes, *event_processes)
        restriction_changes = (*restriction_changes, *event_restrictions)
        obligation_changes = (*obligation_changes, *event_obligations)
        work_order_changes = (*work_order_changes, *event_work_orders)
        evidence_created = (*evidence_created, *event_evidence)
        evidence_sources_changed = (*evidence_sources_changed, *event_sources)
        evidence_treatments_changed = (
            *evidence_treatments_changed,
            *event_treatments,
        )
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
        applied_event_ids=applied_event_ids,
        applied_event_types=applied_event_types,
        processes_changed=_unique(process_changes),
        restrictions_changed=_unique(restriction_changes),
        obligations_changed=_unique(obligation_changes),
        work_orders_changed=_unique(work_order_changes),
        evidence_created=_unique(evidence_created),
        evidence_sources_changed=_unique(evidence_sources_changed),
        evidence_treatments_changed=_unique(evidence_treatments_changed),
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
