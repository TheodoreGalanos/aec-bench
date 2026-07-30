# ABOUTME: Defines immutable stewardship records for the synthetic wastewater pump station.
# ABOUTME: Keeps proposals, authority, obligations, processes, events, and receipts task-local.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import NoReturn

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpInspectionObservation,
    PumpStationChangeKind,
    PumpStationEnvironment,
    PumpStationState,
)

PUMP_STATION_RECEIPT_VERSION = "pump-station-transition-receipt.v1"
PUMP_STATION_AUTHORITY_POLICY_VERSION = "pump-station-authority-policy.v1"
PUMP_STATION_TRANSITION_RULE_VERSION = "pump-station-transition-rules.v1"


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


class PumpStationProcessStatus(StrEnum):
    """Current execution state of a timed work process."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class PumpStationEvidenceKind(StrEnum):
    """Typed evidence produced by scheduled pump-station work."""

    INSPECTION = "inspection"
    FUNCTIONAL_CHECKS = "functional_checks"
    POST_MAINTENANCE_VERIFICATION = "post_maintenance_verification"


class PumpStationEventType(StrEnum):
    """Deterministic scheduled event used by the first-world scheduler."""

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
class RequestInspection:
    """Request a scheduled inspection of one named pump."""

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


type PumpStationProposal = (
    ContinueOperation
    | TransferDuty
    | RequestInspection
    | RequestConditionalDeferral
    | RequestObstructionClearance
    | RequestProvisionalReturn
    | RequestProvisionalClosure
    | RequestVerification
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


@dataclass(frozen=True, slots=True)
class PumpStationScheduledEvent:
    """One typed event ordered by time, class priority, and stable identity."""

    event_id: str
    event_type: PumpStationEventType
    scheduled_seconds: int
    process_id: str | None = None
    obligation_id: str | None = None


@dataclass(frozen=True, slots=True)
class PumpStationStewardshipState:
    """Complete in-memory ASW-2A2 state over the pure physical kernel."""

    physical: PumpStationState
    environment: PumpStationEnvironment
    sequence: int
    resources: PumpStationWorkResources
    restrictions: tuple[PumpStationRestriction, ...]
    obligations: tuple[PumpStationObligation, ...]
    work_orders: tuple[PumpStationWorkOrder, ...]
    processes: tuple[PumpStationProcess, ...]
    evidence: tuple[PumpStationEvidence, ...]
    scheduled_events: tuple[PumpStationScheduledEvent, ...]

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

    def __post_init__(self) -> None:
        if self.receipt_version != PUMP_STATION_RECEIPT_VERSION:
            _fail("receipt-version", self.receipt_version)
        if self.authority_policy_version != PUMP_STATION_AUTHORITY_POLICY_VERSION:
            _fail("authority-policy-version", self.authority_policy_version)
        if self.transition_rule_version != PUMP_STATION_TRANSITION_RULE_VERSION:
            _fail("transition-rule-version", self.transition_rule_version)


@dataclass(frozen=True, slots=True)
class PumpStationTransition:
    """New state and receipt returned by one state-machine operation."""

    state: PumpStationStewardshipState
    receipt: PumpStationTransitionReceipt
