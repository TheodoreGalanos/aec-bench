# ABOUTME: Defines immutable stewardship records for the synthetic wastewater pump station.
# ABOUTME: Keeps proposals, authority, obligations, processes, events, and receipts task-local.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, NoReturn, TypeVar, cast

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogItem,
    PumpStationBacklogStatus,
    PumpStationCoupledProcess,
    PumpStationPoolReservation,
    PumpStationResourceState,
    PumpStationWorkGenerationRecord,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PumpStationEvidenceHealth,
    PumpStationEvidenceTreatment,
    PumpStationObservationSource,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpInspectionObservation,
    PumpStationChangeKind,
    PumpStationCoupledEnvironment,
    PumpStationCoupledOperatingInterval,
    PumpStationCoupledPhysicalState,
    PumpStationDutyAssignment,
    PumpStationEnvironment,
    PumpStationObservation,
    PumpStationOutageEpisode,
    PumpStationServiceRequirement,
    PumpStationState,
)

PUMP_STATION_STATE_VERSION_V1 = "pump-station-stewardship-state.v1"
PUMP_STATION_STATE_VERSION_V2 = "pump-station-stewardship-state.v2"
PUMP_STATION_STATE_VERSION_V3 = "pump-station-stewardship-state.v3"
PUMP_STATION_STATE_VERSION_V4 = "pump-station-stewardship-state.v4"
PUMP_STATION_RECEIPT_VERSION_V1 = "pump-station-transition-receipt.v1"
PUMP_STATION_RECEIPT_VERSION_V2 = "pump-station-transition-receipt.v2"
PUMP_STATION_RECEIPT_VERSION_V3 = "pump-station-transition-receipt.v3"
PUMP_STATION_RECEIPT_VERSION_V4 = "pump-station-transition-receipt.v4"
PUMP_STATION_AUTHORITY_POLICY_VERSION_V1 = "pump-station-authority-policy.v1"
PUMP_STATION_AUTHORITY_POLICY_VERSION_V2 = "pump-station-authority-policy.v2"
PUMP_STATION_AUTHORITY_POLICY_VERSION_V3 = "pump-station-authority-policy.v3"
PUMP_STATION_AUTHORITY_POLICY_VERSION_V4 = "pump-station-authority-policy.v4"
PUMP_STATION_TRANSITION_RULE_VERSION_V1 = "pump-station-transition-rules.v1"
PUMP_STATION_TRANSITION_RULE_VERSION_V2 = "pump-station-transition-rules.v2"
PUMP_STATION_TRANSITION_RULE_VERSION_V3 = "pump-station-transition-rules.v3"
PUMP_STATION_TRANSITION_RULE_VERSION_V4 = "pump-station-transition-rules.v4"

PUMP_STATION_RECEIPT_VERSION = PUMP_STATION_RECEIPT_VERSION_V1
PUMP_STATION_AUTHORITY_POLICY_VERSION = PUMP_STATION_AUTHORITY_POLICY_VERSION_V1
PUMP_STATION_TRANSITION_RULE_VERSION = PUMP_STATION_TRANSITION_RULE_VERSION_V1

_SUPPORTED_RECEIPT_VERSIONS = {
    PUMP_STATION_RECEIPT_VERSION_V1,
    PUMP_STATION_RECEIPT_VERSION_V2,
    PUMP_STATION_RECEIPT_VERSION_V3,
}
_SUPPORTED_AUTHORITY_POLICY_VERSIONS = {
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V1,
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V2,
    PUMP_STATION_AUTHORITY_POLICY_VERSION_V3,
}
_SUPPORTED_TRANSITION_RULE_VERSIONS = {
    PUMP_STATION_TRANSITION_RULE_VERSION_V1,
    PUMP_STATION_TRANSITION_RULE_VERSION_V2,
    PUMP_STATION_TRANSITION_RULE_VERSION_V3,
}
_SUPPORTED_STATE_VERSIONS = {
    PUMP_STATION_STATE_VERSION_V1,
    PUMP_STATION_STATE_VERSION_V2,
    PUMP_STATION_STATE_VERSION_V3,
    PUMP_STATION_STATE_VERSION_V4,
}


class PumpStationProposalError(ValueError):
    """Raised when a proposal or scheduled transition leaves the task contract."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationProposalError(code, detail)


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        _fail("proposal-shape", f"{field_name} must not be empty")


def _require_non_negative(value: int, field_name: str) -> None:
    if value < 0:
        _fail("stewardship-state", f"{field_name} must be non-negative")


class PumpStationAuthority(StrEnum):
    """Task-local authority capability."""

    OPERATIONS = "operations"
    MAINTENANCE = "maintenance"
    ENGINEERING = "engineering"
    WORK_MANAGEMENT = "work_management"
    VERIFICATION = "verification"


class PumpStationAuthorityOutcome(StrEnum):
    """Result of applying the first-world authority policy."""

    PERMITTED = "permitted"
    PERMITTED_WITH_CONDITIONS = "permitted_with_conditions"
    DENIED = "denied"
    DEFERRED_PENDING_PREREQUISITES = "deferred_pending_prerequisites"
    INVALID = "invalid"


class PumpStationExecutionOutcome(StrEnum):
    """Result of executing or cancelling an authorised transition."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


class PumpStationRestrictionKind(StrEnum):
    """Operating restriction supported by the first pump-station world."""

    DEFERRED_PUMP_NOT_DUTY = "deferred_pump_not_duty"
    POST_MAINTENANCE_RUN_IN = "post_maintenance_run_in"
    NO_INTERVENTION = "no_intervention"


class PumpStationRestrictionStatus(StrEnum):
    """Current state of one operating restriction."""

    ACTIVE = "active"
    LIFTED = "lifted"


class PumpStationObligationKind(StrEnum):
    """Durable duty supported by the first pump-station world."""

    DEFERRED_FOLLOW_UP = "deferred_follow_up"
    POST_MAINTENANCE_VERIFICATION = "post_maintenance_verification"


class PumpStationObligationStatus(StrEnum):
    """Lifecycle state supported by the first-world obligation policy."""

    ACTIVE = "active"
    DUE = "due"
    OVERDUE = "overdue"
    FULFILLED = "fulfilled"
    BREACHED = "breached"


class PumpStationWorkOrderStatus(StrEnum):
    """Administrative state of the first-world work order."""

    OPEN = "open"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    SCOPE_COMPLETED = "scope_completed"
    PROVISIONALLY_CLOSED = "provisionally_closed"


class PumpStationProcessKind(StrEnum):
    """Timed work process supported by the first-world schedule."""

    INSPECTION = "inspection"
    OBSTRUCTION_CLEARANCE = "obstruction_clearance"
    FUNCTIONAL_CHECKS = "functional_checks"
    POST_MAINTENANCE_VERIFICATION = "post_maintenance_verification"
    ACCESS_PREPARATION = "access_preparation"
    REPAIR_KIT_DELIVERY = "repair_kit_delivery"


class PumpStationProcessStatus(StrEnum):
    """Current execution state of a timed work process."""

    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


class PumpStationDependencyKind(StrEnum):
    """Fixed dependency classes used by rich pump-station work."""

    PHYSICAL = "physical"
    SAFETY = "safety"
    EVIDENCE = "evidence"
    RESOURCE = "resource"
    ADMINISTRATIVE_CLOSEOUT = "administrative_closeout"


class PumpStationResourceKind(StrEnum):
    """Reservable work resources in the rich pump-station scenario."""

    ACCESS = "access"
    REPAIR_KIT = "repair_kit"
    INTERVENTION_SLOT = "intervention_slot"


class PumpStationEvidenceKind(StrEnum):
    """Typed evidence produced by scheduled pump-station work."""

    INSPECTION = "inspection"
    FUNCTIONAL_CHECKS = "functional_checks"
    POST_MAINTENANCE_VERIFICATION = "post_maintenance_verification"
    CONDITION_CHECK = "condition_check"


class PumpStationEventType(StrEnum):
    """Deterministic scheduled event used by the first-world scheduler."""

    DECISION_POINT = "decision_point"
    EVIDENCE_TREATMENT_ACTIVATION = "evidence_treatment_activation"
    EVIDENCE_RELEASE = "evidence_release"
    OBLIGATION_DUE = "obligation_due"
    OBLIGATION_OVERDUE = "obligation_overdue"
    OBLIGATION_BREACH = "obligation_breach"
    ACCESS_AVAILABLE = "access_available"
    ACCESS_WITHDRAWN = "access_withdrawn"
    REPAIR_KIT_AVAILABLE = "repair_kit_available"
    PROCESS_COMPLETION = "process_completion"


@dataclass(frozen=True, slots=True)
class ProposalContext:
    """Identity and state binding shared by every first-world proposal."""

    proposal_id: str
    agent_tenure_id: str
    based_on_sequence: int
    base_view_id: str
    information_set_id: str
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.proposal_id, "proposal_id")
        _require_text(self.agent_tenure_id, "agent_tenure_id")
        _require_non_negative(self.based_on_sequence, "based_on_sequence")
        _require_text(self.base_view_id, "base_view_id")
        _require_text(self.information_set_id, "information_set_id")
        _require_text(self.reason, "reason")


@dataclass(frozen=True, slots=True)
class ContinueOperation:
    """Continue the permitted mode until the next decision-relevant event."""

    context: ProposalContext


@dataclass(frozen=True, slots=True)
class TransferDuty:
    """Transfer duty once from the current pump to the standby pump."""

    context: ProposalContext


@dataclass(frozen=True, slots=True)
class RequestDutyAssignment:
    """Request one ordered ASW-8 service assignment through Operations."""

    context: ProposalContext
    ordered_pump_ids: tuple[str, ...]
    source_outage_id: str | None = None
    source_backlog_item_id: str | None = None
    proposal_version: str = "request_duty_assignment.v1"

    def __post_init__(self) -> None:
        if self.proposal_version != "request_duty_assignment.v1":
            raise ValueError("unsupported duty-assignment proposal version")
        if not self.ordered_pump_ids or len(self.ordered_pump_ids) > 2:
            raise ValueError("ordered_pump_ids must contain one or two pumps")
        if len(set(self.ordered_pump_ids)) != len(self.ordered_pump_ids):
            raise ValueError("ordered_pump_ids must not contain duplicates")
        for pump_id in self.ordered_pump_ids:
            _require_text(pump_id, "ordered_pump_ids")
        if self.source_outage_id is not None:
            _require_text(self.source_outage_id, "source_outage_id")
        if self.source_backlog_item_id is not None:
            _require_text(self.source_backlog_item_id, "source_backlog_item_id")


@dataclass(frozen=True, slots=True)
class RequestInspection:
    """Request a scheduled inspection of one named pump."""

    context: ProposalContext
    pump_id: str

    def __post_init__(self) -> None:
        _require_text(self.pump_id, "pump_id")


@dataclass(frozen=True, slots=True)
class RequestConditionCheck:
    """Request one sensor-based condition check for a named pump."""

    context: ProposalContext
    pump_id: str

    def __post_init__(self) -> None:
        _require_text(self.pump_id, "pump_id")


@dataclass(frozen=True, slots=True)
class RequestConditionalDeferral:
    """Request the fixed transfer-then-isolate deferral."""

    context: ProposalContext
    pump_id: str

    def __post_init__(self) -> None:
        _require_text(self.pump_id, "pump_id")


@dataclass(frozen=True, slots=True)
class RequestObstructionClearance:
    """Request obstruction clearance against named inspection evidence."""

    context: ProposalContext
    pump_id: str
    inspection_evidence_id: str

    def __post_init__(self) -> None:
        _require_text(self.pump_id, "pump_id")
        _require_text(self.inspection_evidence_id, "inspection_evidence_id")


@dataclass(frozen=True, slots=True)
class RequestFunctionalCheck:
    """Request one controlled ASW-8 test against exact current work demand."""

    context: ProposalContext
    pump_id: str
    backlog_item_id: str
    proposal_version: str = "request_functional_check.v1"

    def __post_init__(self) -> None:
        if self.proposal_version != "request_functional_check.v1":
            raise ValueError("unsupported functional-check proposal version")
        _require_text(self.pump_id, "pump_id")
        _require_text(self.backlog_item_id, "backlog_item_id")


@dataclass(frozen=True, slots=True)
class RequestProvisionalReturn:
    """Request provisional return against accepted functional-check evidence."""

    context: ProposalContext
    pump_id: str
    functional_check_evidence_id: str

    def __post_init__(self) -> None:
        _require_text(self.pump_id, "pump_id")
        _require_text(
            self.functional_check_evidence_id,
            "functional_check_evidence_id",
        )


@dataclass(frozen=True, slots=True)
class RequestProvisionalClosure:
    """Request administrative closure while verification remains open."""

    context: ProposalContext
    work_order_id: str

    def __post_init__(self) -> None:
        _require_text(self.work_order_id, "work_order_id")


@dataclass(frozen=True, slots=True)
class RequestVerification:
    """Request independent post-maintenance verification."""

    context: ProposalContext
    pump_id: str

    def __post_init__(self) -> None:
        _require_text(self.pump_id, "pump_id")


@dataclass(frozen=True, slots=True)
class ResumeProcess:
    """Request safe continuation of blocked or suspended work."""

    context: ProposalContext
    process_id: str

    def __post_init__(self) -> None:
        _require_text(self.process_id, "process_id")


@dataclass(frozen=True, slots=True)
class CancelProcess:
    """Request cancellation of live work and release of unused resources."""

    context: ProposalContext
    process_id: str

    def __post_init__(self) -> None:
        _require_text(self.process_id, "process_id")


@dataclass(frozen=True, slots=True)
class RequestDependencyWaiver:
    """Request a Work Management waiver for one administrative dependency."""

    context: ProposalContext
    process_id: str
    dependency_id: str
    evidence_id: str

    def __post_init__(self) -> None:
        _require_text(self.process_id, "process_id")
        _require_text(self.dependency_id, "dependency_id")
        _require_text(self.evidence_id, "evidence_id")


type PumpStationProposal = (
    ContinueOperation
    | TransferDuty
    | RequestDutyAssignment
    | RequestInspection
    | RequestConditionCheck
    | RequestConditionalDeferral
    | RequestObstructionClearance
    | RequestFunctionalCheck
    | RequestProvisionalReturn
    | RequestProvisionalClosure
    | RequestVerification
    | ResumeProcess
    | CancelProcess
    | RequestDependencyWaiver
)


@dataclass(frozen=True, slots=True)
class PumpStationAuthorityDecision:
    """Authority result recorded separately from execution."""

    outcome: PumpStationAuthorityOutcome
    required_authorities: tuple[PumpStationAuthority, ...]
    detail: str


@dataclass(frozen=True, slots=True)
class PumpStationSchedule:
    """Relative first-world schedule for access and repair-kit availability."""

    access_available_after_seconds: int
    repair_kit_available_after_seconds: int
    access_withdrawal_after_seconds: int | None = None
    access_restored_after_seconds: int | None = None
    decision_point_after_seconds: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        _require_non_negative(
            self.access_available_after_seconds,
            "access_available_after_seconds",
        )
        _require_non_negative(
            self.repair_kit_available_after_seconds,
            "repair_kit_available_after_seconds",
        )
        if self.access_withdrawal_after_seconds is not None:
            _require_non_negative(
                self.access_withdrawal_after_seconds,
                "access_withdrawal_after_seconds",
            )
        if self.access_restored_after_seconds is not None:
            _require_non_negative(
                self.access_restored_after_seconds,
                "access_restored_after_seconds",
            )
            if self.access_withdrawal_after_seconds is None:
                raise ValueError("access restoration requires one access withdrawal")
            if self.access_restored_after_seconds <= self.access_withdrawal_after_seconds:
                raise ValueError("access restoration must follow access withdrawal")
        for value in self.decision_point_after_seconds:
            _require_non_negative(value, "decision_point_after_seconds")
        if len(set(self.decision_point_after_seconds)) != len(self.decision_point_after_seconds):
            raise ValueError("decision_point_after_seconds must not contain duplicates")


@dataclass(frozen=True, slots=True)
class PumpStationWorkResources:
    """Current access, repair-kit, and intervention capacity."""

    access_window_seconds: int
    repair_kit_available: bool
    available_intervention_slots: int

    def __post_init__(self) -> None:
        _require_non_negative(
            self.access_window_seconds,
            "access_window_seconds",
        )
        _require_non_negative(
            self.available_intervention_slots,
            "available_intervention_slots",
        )


@dataclass(frozen=True, slots=True)
class PumpStationRestriction:
    """One authority-owned operating restriction."""

    restriction_id: str
    kind: PumpStationRestrictionKind
    pump_id: str
    status: PumpStationRestrictionStatus
    created_sequence: int
    evidence_id: str | None = None
    parent_restriction_id: str | None = None


@dataclass(frozen=True, slots=True)
class PumpStationObligation:
    """One durable calendar-or-runtime obligation."""

    obligation_id: str
    kind: PumpStationObligationKind
    pump_id: str
    status: PumpStationObligationStatus
    originating_proposal_id: str
    responsible_authority: PumpStationAuthority
    linked_restriction_id: str
    due_calendar_seconds: int
    due_runtime_seconds: int
    created_sequence: int
    evidence_id: str | None = None


@dataclass(frozen=True, slots=True)
class PumpStationWorkOrder:
    """Administrative container for work on one pump."""

    work_order_id: str
    pump_id: str
    status: PumpStationWorkOrderStatus
    created_sequence: int


@dataclass(frozen=True, slots=True)
class PumpStationProcess:
    """Timed work that can complete, fail, or be interrupted."""

    process_id: str
    kind: PumpStationProcessKind
    pump_id: str
    work_order_id: str
    status: PumpStationProcessStatus
    started_at_seconds: int
    completion_at_seconds: int
    performer: PumpStationAuthority
    source_evidence_id: str | None = None
    remaining_duration_seconds: int | None = None
    dependency_ids: tuple[str, ...] = ()
    suspended_at_seconds: int | None = None
    cancelled_at_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.remaining_duration_seconds is not None:
            _require_non_negative(
                self.remaining_duration_seconds,
                "remaining_duration_seconds",
            )
        if len(set(self.dependency_ids)) != len(self.dependency_ids):
            _fail("stewardship-state", "process dependency_ids must be distinct")


@dataclass(frozen=True, slots=True)
class PumpStationProcessDependency:
    """One fixed AND dependency for a named work process."""

    dependency_id: str
    process_id: str
    kind: PumpStationDependencyKind
    detail: str
    satisfied: bool
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.dependency_id, "dependency_id")
        _require_text(self.process_id, "process_id")
        _require_text(self.detail, "detail")


@dataclass(frozen=True, slots=True)
class PumpStationDependencyWaiver:
    """Approved waiver of one administrative closeout dependency."""

    waiver_id: str
    process_id: str
    dependency_id: str
    evidence_id: str
    approved_by: PumpStationAuthority
    created_sequence: int

    def __post_init__(self) -> None:
        _require_text(self.waiver_id, "waiver_id")
        _require_text(self.process_id, "process_id")
        _require_text(self.dependency_id, "dependency_id")
        _require_text(self.evidence_id, "evidence_id")
        _require_non_negative(self.created_sequence, "created_sequence")


@dataclass(frozen=True, slots=True)
class PumpStationResourceReservation:
    """One live reservation of a bounded shared work resource."""

    reservation_id: str
    kind: PumpStationResourceKind
    process_id: str
    created_sequence: int

    def __post_init__(self) -> None:
        _require_text(self.reservation_id, "reservation_id")
        _require_text(self.process_id, "process_id")
        _require_non_negative(self.created_sequence, "created_sequence")


@dataclass(frozen=True, slots=True)
class PumpStationEvidence:
    """Typed evidence separated from latent physical state."""

    evidence_id: str
    kind: PumpStationEvidenceKind
    pump_id: str
    created_at_seconds: int
    produced_by: PumpStationAuthority
    accepted_by: PumpStationAuthority | None
    inspection: PumpInspectionObservation | None = None
    passed: bool | None = None
    health: PumpStationEvidenceHealth | None = None
    condition_observation: PumpStationObservation | None = None


@dataclass(frozen=True, slots=True)
class PumpStationPendingEvidence:
    """One produced evidence item held until its fixed availability time."""

    evidence: PumpStationEvidence
    treatment_id: str
    release_at_seconds: int

    def __post_init__(self) -> None:
        _require_text(self.treatment_id, "treatment_id")
        _require_non_negative(self.release_at_seconds, "release_at_seconds")


@dataclass(frozen=True, slots=True)
class PumpStationScheduledEvent:
    """One typed event ordered by time, class priority, and stable identity."""

    event_id: str
    event_type: PumpStationEventType
    scheduled_seconds: int
    process_id: str | None = None
    obligation_id: str | None = None
    treatment_id: str | None = None
    evidence_id: str | None = None


_PhysicalStateT = TypeVar(
    "_PhysicalStateT",
    PumpStationState,
    PumpStationCoupledPhysicalState,
    default=PumpStationState,
)
_EnvironmentT = TypeVar(
    "_EnvironmentT",
    PumpStationEnvironment,
    PumpStationCoupledEnvironment,
    default=PumpStationEnvironment,
)
_ResourceStateT = TypeVar(
    "_ResourceStateT",
    PumpStationWorkResources,
    PumpStationResourceState,
    default=PumpStationWorkResources,
)
_ProcessT = TypeVar(
    "_ProcessT",
    PumpStationProcess,
    PumpStationCoupledProcess,
    default=PumpStationProcess,
)
_ReservationT = TypeVar(
    "_ReservationT",
    PumpStationResourceReservation,
    PumpStationPoolReservation,
    default=PumpStationResourceReservation,
)


@dataclass(frozen=True, slots=True)
class PumpStationStewardshipState(
    Generic[_PhysicalStateT, _EnvironmentT, _ResourceStateT, _ProcessT, _ReservationT],
):
    """Complete in-memory ASW-2A2 state over the pure physical kernel."""

    physical: _PhysicalStateT
    environment: _EnvironmentT
    sequence: int
    resources: _ResourceStateT
    restrictions: tuple[PumpStationRestriction, ...]
    obligations: tuple[PumpStationObligation, ...]
    work_orders: tuple[PumpStationWorkOrder, ...]
    processes: tuple[_ProcessT, ...]
    evidence: tuple[PumpStationEvidence, ...]
    scheduled_events: tuple[PumpStationScheduledEvent, ...]
    state_version: str = PUMP_STATION_STATE_VERSION_V1
    dependencies: tuple[PumpStationProcessDependency, ...] = ()
    dependency_waivers: tuple[PumpStationDependencyWaiver, ...] = ()
    resource_reservations: tuple[_ReservationT, ...] = ()
    evidence_sources: tuple[PumpStationObservationSource, ...] = ()
    evidence_treatments: tuple[PumpStationEvidenceTreatment, ...] = ()
    pending_evidence: tuple[PumpStationPendingEvidence, ...] = ()
    assignment: PumpStationDutyAssignment = field(default=cast(PumpStationDutyAssignment, None))
    service_schedule: tuple[PumpStationServiceRequirement, ...] = ()
    baseline_schedule: tuple[tuple[int, int, tuple[str, ...]], ...] = ()
    disclosed_through_calendar_seconds: int = 0
    backlog: tuple[PumpStationBacklogItem, ...] = ()
    generation_records: tuple[PumpStationWorkGenerationRecord, ...] = ()
    outage_episodes: tuple[PumpStationOutageEpisode, ...] = ()
    operating_intervals: tuple[PumpStationCoupledOperatingInterval, ...] = ()
    collateral_runtime: tuple[tuple[str, str, int], ...] = ()
    pending_start_pump_ids: tuple[str, ...] = ()
    event_effect_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state_version not in _SUPPORTED_STATE_VERSIONS:
            _fail("state-version", self.state_version)
        if self.state_version == PUMP_STATION_STATE_VERSION_V4:
            if not isinstance(self.physical, PumpStationCoupledPhysicalState) or not isinstance(
                self.environment,
                PumpStationCoupledEnvironment,
            ):
                _fail("state-version", "version 4 requires coupled physical records")
            if not isinstance(self.resources, PumpStationResourceState):
                _fail("state-version", "version 4 requires resource pools")
            if self.assignment is None:
                _fail("state-version", "version 4 requires a duty assignment")
            if any(not isinstance(process, PumpStationCoupledProcess) for process in self.processes) or any(
                not isinstance(reservation, PumpStationPoolReservation) for reservation in self.resource_reservations
            ):
                _fail("state-version", "version 4 process or reservation profile differs")
            if len({item.item_id for item in self.backlog}) != len(self.backlog):
                _fail("backlog-identity", "backlog item IDs must be distinct")
            return
        if (
            not isinstance(self.physical, PumpStationState)
            or not isinstance(self.environment, PumpStationEnvironment)
            or not isinstance(self.resources, PumpStationWorkResources)
            or any(isinstance(process, PumpStationCoupledProcess) for process in self.processes)
            or any(isinstance(reservation, PumpStationPoolReservation) for reservation in self.resource_reservations)
        ):
            _fail("state-version", "version 1 to 3 requires legacy state records")
        reservation_kinds: list[PumpStationResourceKind] = []
        for reservation in self.resource_reservations:
            if not isinstance(reservation, PumpStationResourceReservation):
                _fail("state-version", "version 1 to 3 requires legacy reservations")
            reservation_kinds.append(reservation.kind)
        if len(set(reservation_kinds)) != len(reservation_kinds):
            _fail("resource-reservation", "a resource has more than one reservation")
        if self.state_version == PUMP_STATION_STATE_VERSION_V1 and (
            self.dependencies or self.dependency_waivers or self.resource_reservations
        ):
            _fail("state-version", "version 1 cannot contain rich-work records")
        if self.state_version not in {
            PUMP_STATION_STATE_VERSION_V3,
            PUMP_STATION_STATE_VERSION_V4,
        } and (self.evidence_sources or self.evidence_treatments or self.pending_evidence):
            _fail("state-version", "only version 3 can contain evidence-health records")

    @property
    def state_id(self) -> str:
        """Return the complete canonical state identity for the selected profile."""
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
            stewardship_state_id,
        )

        return stewardship_state_id(cast(Any, self))

    @property
    def calendar_seconds(self) -> int:
        """Return the current physical calendar time."""
        return self.physical.calendar_seconds

    @property
    def accepted_evidence_ids(self) -> tuple[str, ...]:
        """Derive accepted evidence identities from canonical evidence records."""
        return tuple(
            item.evidence_id
            for item in self.evidence
            if item.accepted_by is not None and (item.health is None or item.health.accepted)
        )

    @property
    def active_restriction_ids(self) -> tuple[str, ...]:
        """Derive active restriction identities from their owner records."""
        return tuple(
            item.restriction_id for item in self.restrictions if item.status is PumpStationRestrictionStatus.ACTIVE
        )

    @property
    def active_liability_ids(self) -> tuple[str, ...]:
        """Derive current liabilities from obligations, outages, and durable work."""
        obligation_ids: tuple[str, ...] = tuple(
            item.obligation_id for item in self.obligations if item.status is not PumpStationObligationStatus.FULFILLED
        )
        outage_ids: tuple[str, ...] = tuple(item.episode_id for item in self.outage_episodes if item.status == "open")
        work_ids: tuple[str, ...] = tuple(
            item.item_id
            for item in self.backlog
            if item.generation_rule_id in {"WG-06", "WG-07"}
            and item.status
            not in {
                PumpStationBacklogStatus.CLOSED,
                PumpStationBacklogStatus.CANCELLED,
                PumpStationBacklogStatus.SUPERSEDED,
            }
        )
        return (*obligation_ids, *outage_ids, *work_ids)

    @property
    def created_liability_ids(self) -> tuple[str, ...]:
        """Derive non-opening liability identities from canonical owner records."""
        obligation_ids: tuple[str, ...] = tuple(
            item.obligation_id for item in self.obligations if item.created_sequence > 0
        )
        work_ids: tuple[str, ...] = tuple(
            item.item_id for item in self.backlog if item.generation_rule_id in {"WG-06", "WG-07"}
        )
        return (*obligation_ids, *work_ids)

    @property
    def discharged_liability_ids(self) -> tuple[str, ...]:
        """Derive discharged liabilities without a second mutable ledger."""
        obligation_ids: tuple[str, ...] = tuple(
            item.obligation_id for item in self.obligations if item.status is PumpStationObligationStatus.FULFILLED
        )
        outage_ids: tuple[str, ...] = tuple(item.episode_id for item in self.outage_episodes if item.status == "closed")
        work_ids: tuple[str, ...] = tuple(
            item.item_id
            for item in self.backlog
            if item.generation_rule_id in {"WG-06", "WG-07"} and item.status is PumpStationBacklogStatus.CLOSED
        )
        return (*obligation_ids, *outage_ids, *work_ids)

    @property
    def terminal_work_item_ids(self) -> tuple[str, ...]:
        """Derive terminal work identities from the canonical backlog records."""
        terminal_statuses = {
            PumpStationBacklogStatus.CLOSED,
            PumpStationBacklogStatus.CANCELLED,
            PumpStationBacklogStatus.SUPERSEDED,
        }
        return tuple(item.item_id for item in self.backlog if item.status in terminal_statuses)

    def backlog_item(self, item_id: str) -> PumpStationBacklogItem:
        """Return one current v4 backlog item by actor-visible identity."""
        for item in self.backlog:
            if item.item_id == item_id:
                return item
        _fail("unknown-backlog-item", item_id)

    def restriction(
        self,
        kind: PumpStationRestrictionKind,
        pump_id: str,
    ) -> PumpStationRestriction:
        """Return the latest matching restriction."""
        for restriction in reversed(self.restrictions):
            if restriction.kind is kind and restriction.pump_id == pump_id:
                return restriction
        raise LookupError(f"missing restriction {kind.value} for {pump_id}")

    def obligation(
        self,
        kind: PumpStationObligationKind,
        pump_id: str,
    ) -> PumpStationObligation:
        """Return the latest matching obligation."""
        for obligation in reversed(self.obligations):
            if obligation.kind is kind and obligation.pump_id == pump_id:
                return obligation
        raise LookupError(f"missing obligation {kind.value} for {pump_id}")

    def work_order_for(self, pump_id: str) -> PumpStationWorkOrder:
        """Return the work order for one pump."""
        for work_order in reversed(self.work_orders):
            if work_order.pump_id == pump_id:
                return work_order
        raise LookupError(f"missing work order for {pump_id}")

    def process(
        self,
        process_id: str,
    ) -> _ProcessT:
        """Return one process by identity."""
        for process in self.processes:
            if process.process_id == process_id:
                return process
        raise LookupError(f"missing process {process_id}")

    def dependency(self, dependency_id: str) -> PumpStationProcessDependency:
        """Return one process dependency by identity."""
        for dependency in self.dependencies:
            if dependency.dependency_id == dependency_id:
                return dependency
        raise LookupError(f"missing dependency {dependency_id}")

    def latest_inspection(self, pump_id: str) -> PumpStationEvidence:
        """Return the latest inspection evidence for one pump."""
        return self._latest_evidence(PumpStationEvidenceKind.INSPECTION, pump_id)

    def latest_functional_checks(self, pump_id: str) -> PumpStationEvidence:
        """Return the latest functional-check evidence for one pump."""
        return self._latest_evidence(
            PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
            pump_id,
        )

    def _latest_evidence(
        self,
        kind: PumpStationEvidenceKind,
        pump_id: str,
    ) -> PumpStationEvidence:
        for evidence in reversed(self.evidence):
            if evidence.kind is kind and evidence.pump_id == pump_id:
                return evidence
        raise LookupError(f"missing {kind.value} evidence for {pump_id}")


@dataclass(frozen=True, slots=True)
class PumpStationTransitionReceipt:
    """Immutable in-memory record of one applied state-machine transition."""

    receipt_version: str
    authority_policy_version: str
    transition_rule_version: str
    transition_id: str
    sequence: int
    trigger: str
    proposal_id: str | None
    authority: PumpStationAuthorityDecision | None
    execution: PumpStationExecutionOutcome
    pre_state_id: str
    post_state_id: str
    clock_delta_seconds: int
    applied_event_ids: tuple[str, ...]
    applied_event_types: tuple[PumpStationEventType, ...]
    processes_changed: tuple[str, ...]
    restrictions_changed: tuple[str, ...]
    obligations_changed: tuple[str, ...]
    work_orders_changed: tuple[str, ...]
    evidence_created: tuple[str, ...]
    physical_change: PumpStationChangeKind | None
    evidence_sources_changed: tuple[str, ...] = ()
    evidence_treatments_changed: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.receipt_version not in _SUPPORTED_RECEIPT_VERSIONS:
            _fail("receipt-version", self.receipt_version)
        if self.authority_policy_version not in _SUPPORTED_AUTHORITY_POLICY_VERSIONS:
            _fail("authority-policy-version", self.authority_policy_version)
        if self.transition_rule_version not in _SUPPORTED_TRANSITION_RULE_VERSIONS:
            _fail("transition-rule-version", self.transition_rule_version)
        expected = {
            PUMP_STATION_RECEIPT_VERSION_V1: (
                PUMP_STATION_AUTHORITY_POLICY_VERSION_V1,
                PUMP_STATION_TRANSITION_RULE_VERSION_V1,
            ),
            PUMP_STATION_RECEIPT_VERSION_V2: (
                PUMP_STATION_AUTHORITY_POLICY_VERSION_V2,
                PUMP_STATION_TRANSITION_RULE_VERSION_V2,
            ),
            PUMP_STATION_RECEIPT_VERSION_V3: (
                PUMP_STATION_AUTHORITY_POLICY_VERSION_V3,
                PUMP_STATION_TRANSITION_RULE_VERSION_V3,
            ),
        }[self.receipt_version]
        if (
            self.authority_policy_version,
            self.transition_rule_version,
        ) != expected:
            _fail("receipt-version", "receipt, policy, and rule versions differ")


@dataclass(frozen=True, slots=True)
class PumpStationTransition:
    """New state and receipt returned by one state-machine operation."""

    state: PumpStationStewardshipState
    receipt: PumpStationTransitionReceipt
