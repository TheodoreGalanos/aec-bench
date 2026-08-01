# ABOUTME: Evaluates the fixed first-world authority policy for pump-station proposals.
# ABOUTME: Keeps authority decisions separate from execution and physical effects.

from __future__ import annotations

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    ObstructionFinding,
    PumpStationModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    CancelProcess,
    ContinueOperation,
    PumpStationAuthority,
    PumpStationAuthorityDecision,
    PumpStationAuthorityOutcome,
    PumpStationDependencyKind,
    PumpStationEvidence,
    PumpStationEvidenceKind,
    PumpStationObligation,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationProcess,
    PumpStationProcessKind,
    PumpStationProcessStatus,
    PumpStationProposal,
    PumpStationRestriction,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
    PumpStationWorkOrder,
    PumpStationWorkOrderStatus,
    RequestConditionalDeferral,
    RequestConditionCheck,
    RequestDependencyWaiver,
    RequestInspection,
    RequestObstructionClearance,
    RequestProvisionalClosure,
    RequestProvisionalReturn,
    RequestVerification,
    ResumeProcess,
    TransferDuty,
)

PROPOSAL_TYPES = (
    ContinueOperation,
    TransferDuty,
    RequestInspection,
    RequestConditionCheck,
    RequestConditionalDeferral,
    RequestObstructionClearance,
    RequestProvisionalReturn,
    RequestProvisionalClosure,
    RequestVerification,
    ResumeProcess,
    CancelProcess,
    RequestDependencyWaiver,
)


def active_restriction(
    state: PumpStationStewardshipState,
    kind: PumpStationRestrictionKind,
    pump_id: str,
) -> PumpStationRestriction | None:
    """Return the current matching restriction, if one exists."""
    for restriction in reversed(state.restrictions):
        if (
            restriction.kind is kind
            and restriction.pump_id == pump_id
            and restriction.status is PumpStationRestrictionStatus.ACTIVE
        ):
            return restriction
    return None


def current_obligation(
    state: PumpStationStewardshipState,
    kind: PumpStationObligationKind,
    pump_id: str,
) -> PumpStationObligation | None:
    """Return the latest matching obligation, if one exists."""
    for obligation in reversed(state.obligations):
        if obligation.kind is kind and obligation.pump_id == pump_id:
            return obligation
    return None


def work_order(
    state: PumpStationStewardshipState,
    work_order_id: str,
) -> PumpStationWorkOrder | None:
    """Return one work order by identity."""
    for item in state.work_orders:
        if item.work_order_id == work_order_id:
            return item
    return None


def work_order_for_pump(
    state: PumpStationStewardshipState,
    pump_id: str,
) -> PumpStationWorkOrder | None:
    """Return the latest work order for one pump."""
    for item in reversed(state.work_orders):
        if item.pump_id == pump_id:
            return item
    return None


def evidence(
    state: PumpStationStewardshipState,
    evidence_id: str,
) -> PumpStationEvidence | None:
    """Return one evidence record by identity."""
    for item in state.evidence:
        if item.evidence_id == evidence_id:
            return item
    return None


def active_process(
    state: PumpStationStewardshipState,
    kind: PumpStationProcessKind,
    pump_id: str,
) -> PumpStationProcess | None:
    """Return the active matching process, if one exists."""
    for process in reversed(state.processes):
        if (
            process.kind is kind
            and process.pump_id == pump_id
            and process.status
            in {
                PumpStationProcessStatus.IN_PROGRESS,
                PumpStationProcessStatus.BLOCKED,
                PumpStationProcessStatus.ACTIVE,
                PumpStationProcessStatus.SUSPENDED,
            }
        ):
            return process
    return None


def _authority(
    outcome: PumpStationAuthorityOutcome,
    required: tuple[PumpStationAuthority, ...],
    detail: str,
) -> PumpStationAuthorityDecision:
    return PumpStationAuthorityDecision(
        outcome=outcome,
        required_authorities=required,
        detail=detail,
    )


def _required_authorities(
    proposal: PumpStationProposal,
) -> tuple[PumpStationAuthority, ...]:
    if isinstance(
        proposal,
        ContinueOperation | TransferDuty | RequestProvisionalReturn | RequestConditionCheck,
    ):
        return (PumpStationAuthority.OPERATIONS,)
    if isinstance(proposal, RequestInspection | RequestObstructionClearance):
        return (
            PumpStationAuthority.MAINTENANCE,
            PumpStationAuthority.OPERATIONS,
        )
    if isinstance(proposal, RequestConditionalDeferral):
        return (
            PumpStationAuthority.ENGINEERING,
            PumpStationAuthority.OPERATIONS,
        )
    if isinstance(proposal, RequestProvisionalClosure):
        return (PumpStationAuthority.WORK_MANAGEMENT,)
    if isinstance(proposal, RequestDependencyWaiver):
        return (PumpStationAuthority.WORK_MANAGEMENT,)
    if isinstance(proposal, CancelProcess | ResumeProcess):
        return (
            PumpStationAuthority.MAINTENANCE,
            PumpStationAuthority.OPERATIONS,
        )
    return (PumpStationAuthority.VERIFICATION,)


def _validate_pump(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    pump_id: str,
) -> bool:
    return pump_id in model.pump_ids and pump_id in {pump.pump_id for pump in state.physical.pumps}


def decide_proposal(
    model: PumpStationModel,
    state: PumpStationStewardshipState,
    proposal: PumpStationProposal,
) -> PumpStationAuthorityDecision:
    """Evaluate a proposal without executing or mutating it."""
    required = _required_authorities(proposal)
    context = proposal.context
    if context.based_on_sequence != state.sequence:
        return _authority(
            PumpStationAuthorityOutcome.INVALID,
            required,
            "proposal is bound to a stale state sequence",
        )
    if isinstance(
        proposal,
        RequestInspection
        | RequestConditionCheck
        | RequestConditionalDeferral
        | RequestObstructionClearance
        | RequestProvisionalReturn
        | RequestVerification,
    ) and not _validate_pump(model, state, proposal.pump_id):
        return _authority(
            PumpStationAuthorityOutcome.INVALID,
            required,
            "proposal names an unknown pump",
        )
    if isinstance(proposal, ContinueOperation):
        blocked = active_restriction(
            state,
            PumpStationRestrictionKind.DEFERRED_PUMP_NOT_DUTY,
            state.physical.duty_pump_id,
        )
        if blocked is not None:
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "the deferred duty pump must transfer before operation continues",
            )
    elif isinstance(proposal, TransferDuty):
        if state.physical.duty_transfer_count >= model.maximum_duty_transfers:
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "the one permitted duty transfer has already occurred",
            )
    elif isinstance(proposal, RequestConditionalDeferral):
        if proposal.pump_id != state.physical.duty_pump_id:
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "the fixed deferral applies only to the current duty pump",
            )
        obligation = current_obligation(
            state,
            PumpStationObligationKind.DEFERRED_FOLLOW_UP,
            proposal.pump_id,
        )
        if obligation is not None and obligation.status is not PumpStationObligationStatus.FULFILLED:
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "an unresolved deferral already exists for the pump",
            )
        return _authority(
            PumpStationAuthorityOutcome.PERMITTED_WITH_CONDITIONS,
            required,
            "permitted under the fixed transfer-then-isolate mitigation",
        )
    elif isinstance(proposal, RequestInspection):
        if (
            active_process(
                state,
                PumpStationProcessKind.INSPECTION,
                proposal.pump_id,
            )
            is not None
        ):
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "an inspection is already in progress",
            )
    elif isinstance(proposal, RequestConditionCheck):
        if not state.state_version.endswith(".v3") or len(state.evidence_sources) != 1:
            return _authority(
                PumpStationAuthorityOutcome.INVALID,
                required,
                "condition check requires the version 3 observation source",
            )
    elif isinstance(proposal, RequestObstructionClearance):
        inspection = evidence(state, proposal.inspection_evidence_id)
        if (
            inspection is None
            or inspection.kind is not PumpStationEvidenceKind.INSPECTION
            or inspection.pump_id != proposal.pump_id
            or inspection.inspection is None
            or (not state.state_version.endswith(".v1") and inspection.accepted_by is None)
        ):
            return _authority(
                PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES,
                required,
                "named accepted inspection evidence is not available",
            )
        if inspection.inspection.obstruction_finding is ObstructionFinding.NO_MATERIAL_CONFIRMED:
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "inspection evidence does not support obstruction clearance",
            )
        if state.physical.duty_pump_id == proposal.pump_id:
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "the affected pump must not be the duty pump",
            )
        if state.state_version.endswith(".v1") and (
            state.resources.access_window_seconds < model.resources.access_duration_seconds
            or state.resources.available_intervention_slots < 1
        ):
            return _authority(
                PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES,
                required,
                "access or intervention capacity is not available",
            )
        if (
            active_process(
                state,
                PumpStationProcessKind.OBSTRUCTION_CLEARANCE,
                proposal.pump_id,
            )
            is not None
        ):
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "obstruction clearance is already in progress",
            )
    elif isinstance(proposal, ResumeProcess):
        try:
            process = state.process(proposal.process_id)
        except LookupError:
            return _authority(
                PumpStationAuthorityOutcome.INVALID,
                required,
                "proposal names an unknown process",
            )
        if process.status not in {
            PumpStationProcessStatus.BLOCKED,
            PumpStationProcessStatus.SUSPENDED,
        }:
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "only blocked or suspended work can resume",
            )
        if any(
            restriction.kind is PumpStationRestrictionKind.NO_INTERVENTION
            and restriction.pump_id == process.pump_id
            and restriction.status is PumpStationRestrictionStatus.ACTIVE
            for restriction in state.restrictions
        ):
            return _authority(
                PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES,
                required,
                "an active no-intervention limit blocks resume",
            )
        return _authority(
            PumpStationAuthorityOutcome.PERMITTED_WITH_CONDITIONS,
            required,
            "resume must recheck all fixed dependencies and reservations",
        )
    elif isinstance(proposal, CancelProcess):
        try:
            process = state.process(proposal.process_id)
        except LookupError:
            return _authority(
                PumpStationAuthorityOutcome.INVALID,
                required,
                "proposal names an unknown process",
            )
        if process.status not in {
            PumpStationProcessStatus.BLOCKED,
            PumpStationProcessStatus.ACTIVE,
            PumpStationProcessStatus.SUSPENDED,
        }:
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "only live work can be cancelled",
            )
    elif isinstance(proposal, RequestDependencyWaiver):
        try:
            process = state.process(proposal.process_id)
            dependency = state.dependency(proposal.dependency_id)
        except LookupError:
            return _authority(
                PumpStationAuthorityOutcome.INVALID,
                required,
                "proposal names an unknown process or dependency",
            )
        named_evidence = evidence(state, proposal.evidence_id)
        if named_evidence is None or named_evidence.accepted_by is None:
            return _authority(
                PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES,
                required,
                "named accepted evidence is not available",
            )
        if dependency.process_id != process.process_id:
            return _authority(
                PumpStationAuthorityOutcome.INVALID,
                required,
                "dependency belongs to another process",
            )
        if dependency.kind is not PumpStationDependencyKind.ADMINISTRATIVE_CLOSEOUT:
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "only administrative closeout can be waived",
            )
    elif isinstance(proposal, RequestProvisionalReturn):
        checks = evidence(state, proposal.functional_check_evidence_id)
        order = work_order_for_pump(state, proposal.pump_id)
        deferred = active_restriction(
            state,
            PumpStationRestrictionKind.DEFERRED_PUMP_NOT_DUTY,
            proposal.pump_id,
        )
        if (
            checks is None
            or checks.kind is not PumpStationEvidenceKind.FUNCTIONAL_CHECKS
            or checks.pump_id != proposal.pump_id
            or checks.passed is not True
            or checks.accepted_by is not PumpStationAuthority.VERIFICATION
            or order is None
            or order.status is not PumpStationWorkOrderStatus.SCOPE_COMPLETED
            or deferred is None
        ):
            return _authority(
                PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES,
                required,
                "accepted functional checks and completed scope are required",
            )
    elif isinstance(proposal, RequestProvisionalClosure):
        order = work_order(state, proposal.work_order_id)
        if order is None:
            return _authority(
                PumpStationAuthorityOutcome.INVALID,
                required,
                "proposal names an unknown work order",
            )
        verification = current_obligation(
            state,
            PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
            order.pump_id,
        )
        if (
            order.status is not PumpStationWorkOrderStatus.SCOPE_COMPLETED
            or verification is None
            or verification.status
            not in {
                PumpStationObligationStatus.ACTIVE,
                PumpStationObligationStatus.DUE,
                PumpStationObligationStatus.OVERDUE,
            }
        ):
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "completed scope and open verification are required",
            )
    elif isinstance(proposal, RequestVerification):
        obligation = current_obligation(
            state,
            PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
            proposal.pump_id,
        )
        if obligation is None or obligation.status not in {
            PumpStationObligationStatus.ACTIVE,
            PumpStationObligationStatus.DUE,
            PumpStationObligationStatus.OVERDUE,
        }:
            return _authority(
                PumpStationAuthorityOutcome.DEFERRED_PENDING_PREREQUISITES,
                required,
                "an open verification obligation is required",
            )
        if (
            active_process(
                state,
                PumpStationProcessKind.POST_MAINTENANCE_VERIFICATION,
                proposal.pump_id,
            )
            is not None
        ):
            return _authority(
                PumpStationAuthorityOutcome.DENIED,
                required,
                "verification is already in progress",
            )
    return _authority(
        PumpStationAuthorityOutcome.PERMITTED,
        required,
        "the fixed first-world policy permits the proposal",
    )
