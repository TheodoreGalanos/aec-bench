# ABOUTME: Defines the unversioned live values for the current coupled pump world.
# ABOUTME: Keeps actor actions, root controls, state, and transition results task-local.

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any, NoReturn, cast

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
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledEnvironment,
    PumpStationCoupledOperatingInterval,
    PumpStationCoupledPhysicalState,
    PumpStationDutyAssignment,
    PumpStationOutageEpisode,
    PumpStationServiceRequirement,
)


class PumpStationActionError(ValueError):
    """Raised when an action or control leaves the current task contract."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationActionError(code, detail)


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        _fail("action-shape", f"{field_name} must not be empty")


def _require_non_negative(value: int, field_name: str) -> None:
    if value < 0:
        _fail("stewardship-state", f"{field_name} must be non-negative")


class PumpStationAuthority(StrEnum):
    OPERATIONS = "operations"
    MAINTENANCE = "maintenance"
    ENGINEERING = "engineering"
    WORK_MANAGEMENT = "work_management"
    VERIFICATION = "verification"


class PumpStationAuthorityOutcome(StrEnum):
    PERMITTED = "permitted"
    PERMITTED_WITH_CONDITIONS = "permitted_with_conditions"
    DENIED = "denied"
    DEFERRED_PENDING_PREREQUISITES = "deferred_pending_prerequisites"
    INVALID = "invalid"


class PumpStationRestrictionKind(StrEnum):
    DEFERRED_PUMP_NOT_DUTY = "deferred_pump_not_duty"
    POST_MAINTENANCE_RUN_IN = "post_maintenance_run_in"
    NO_INTERVENTION = "no_intervention"


class PumpStationRestrictionStatus(StrEnum):
    ACTIVE = "active"
    LIFTED = "lifted"


class PumpStationObligationKind(StrEnum):
    DEFERRED_FOLLOW_UP = "deferred_follow_up"
    POST_MAINTENANCE_VERIFICATION = "post_maintenance_verification"


class PumpStationObligationStatus(StrEnum):
    ACTIVE = "active"
    DUE = "due"
    OVERDUE = "overdue"
    FULFILLED = "fulfilled"
    BREACHED = "breached"


class PumpStationWorkOrderStatus(StrEnum):
    OPEN = "open"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    SCOPE_COMPLETED = "scope_completed"
    PROVISIONALLY_CLOSED = "provisionally_closed"


class PumpStationEvidenceKind(StrEnum):
    INSPECTION = "inspection"
    FUNCTIONAL_CHECKS = "functional_checks"
    POST_MAINTENANCE_VERIFICATION = "post_maintenance_verification"
    CONDITION_CHECK = "condition_check"


@dataclass(frozen=True, slots=True)
class ContinueOperation:
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")


@dataclass(frozen=True, slots=True)
class RequestDutyAssignment:
    reason: str
    ordered_pump_ids: tuple[str, ...]
    source_outage_id: str | None = None
    source_backlog_item_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        if not self.ordered_pump_ids or len(self.ordered_pump_ids) > 2:
            raise ValueError("ordered_pump_ids must contain one or two pumps")
        if len(set(self.ordered_pump_ids)) != len(self.ordered_pump_ids):
            raise ValueError("ordered_pump_ids must not contain duplicates")
        for pump_id in self.ordered_pump_ids:
            _require_text(pump_id, "ordered_pump_ids")
        for value, field_name in (
            (self.source_outage_id, "source_outage_id"),
            (self.source_backlog_item_id, "source_backlog_item_id"),
        ):
            if value is not None:
                _require_text(value, field_name)


@dataclass(frozen=True, slots=True)
class RequestInspection:
    reason: str
    pump_id: str
    backlog_item_id: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        _require_text(self.pump_id, "pump_id")
        _require_text(self.backlog_item_id, "backlog_item_id")


@dataclass(frozen=True, slots=True)
class RequestConditionCheck:
    reason: str
    pump_id: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        _require_text(self.pump_id, "pump_id")


@dataclass(frozen=True, slots=True)
class RequestObstructionClearance:
    reason: str
    pump_id: str
    inspection_evidence_id: str
    backlog_item_id: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        _require_text(self.pump_id, "pump_id")
        _require_text(self.inspection_evidence_id, "inspection_evidence_id")
        _require_text(self.backlog_item_id, "backlog_item_id")


@dataclass(frozen=True, slots=True)
class RequestFunctionalCheck:
    reason: str
    pump_id: str
    backlog_item_id: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        _require_text(self.pump_id, "pump_id")
        _require_text(self.backlog_item_id, "backlog_item_id")


@dataclass(frozen=True, slots=True)
class RequestProvisionalReturn:
    reason: str
    pump_id: str
    functional_check_evidence_id: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        _require_text(self.pump_id, "pump_id")
        _require_text(self.functional_check_evidence_id, "functional_check_evidence_id")


@dataclass(frozen=True, slots=True)
class RequestProvisionalClosure:
    reason: str
    work_order_id: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        _require_text(self.work_order_id, "work_order_id")


@dataclass(frozen=True, slots=True)
class RequestVerification:
    reason: str
    pump_id: str
    backlog_item_id: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        _require_text(self.pump_id, "pump_id")
        _require_text(self.backlog_item_id, "backlog_item_id")


@dataclass(frozen=True, slots=True)
class ResumeProcess:
    reason: str
    process_id: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        _require_text(self.process_id, "process_id")


@dataclass(frozen=True, slots=True)
class CancelProcess:
    reason: str
    process_id: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        _require_text(self.process_id, "process_id")


@dataclass(frozen=True, slots=True)
class RequestDependencyWaiver:
    reason: str
    process_id: str
    dependency_id: str
    evidence_id: str

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        _require_text(self.process_id, "process_id")
        _require_text(self.dependency_id, "dependency_id")
        _require_text(self.evidence_id, "evidence_id")


type PumpStationAction = (
    ContinueOperation
    | RequestDutyAssignment
    | RequestInspection
    | RequestConditionCheck
    | RequestObstructionClearance
    | RequestFunctionalCheck
    | RequestProvisionalReturn
    | RequestProvisionalClosure
    | RequestVerification
    | ResumeProcess
    | CancelProcess
    | RequestDependencyWaiver
)


def pump_station_action_name(action: PumpStationAction) -> str:
    """Return the installed operation name for one task-owned action."""
    names = {
        ContinueOperation: "continue_operation",
        RequestDutyAssignment: "request_duty_assignment",
        RequestInspection: "request_inspection",
        RequestObstructionClearance: "request_obstruction_clearance",
        RequestFunctionalCheck: "request_functional_check",
        RequestProvisionalReturn: "request_provisional_return",
        RequestProvisionalClosure: "request_provisional_closure",
        RequestVerification: "request_post_maintenance_verification",
        ResumeProcess: "resume_process",
        CancelProcess: "cancel_process",
        RequestDependencyWaiver: "request_dependency_waiver",
        RequestConditionCheck: "request_condition_check",
    }
    return names[type(action)]


@dataclass(frozen=True, slots=True)
class PumpStationRestriction:
    restriction_id: str
    kind: PumpStationRestrictionKind
    pump_id: str
    status: PumpStationRestrictionStatus
    created_sequence: int
    evidence_id: str | None = None
    parent_restriction_id: str | None = None


@dataclass(frozen=True, slots=True)
class PumpStationObligation:
    obligation_id: str
    kind: PumpStationObligationKind
    pump_id: str
    status: PumpStationObligationStatus
    originating_action_id: str
    responsible_authority: PumpStationAuthority
    linked_restriction_id: str
    due_calendar_seconds: int
    due_runtime_seconds: int
    created_sequence: int
    evidence_id: str | None = None


@dataclass(frozen=True, slots=True)
class PumpStationWorkOrder:
    work_order_id: str
    pump_id: str
    status: PumpStationWorkOrderStatus
    created_sequence: int


@dataclass(frozen=True, slots=True)
class PumpStationEvidence:
    evidence_id: str
    kind: PumpStationEvidenceKind
    pump_id: str
    created_at_seconds: int
    produced_by: PumpStationAuthority
    accepted_by: PumpStationAuthority | None
    passed: bool | None = None
    health: PumpStationEvidenceHealth | None = None


@dataclass(frozen=True, slots=True)
class PumpStationStewardshipState:
    """Complete unversioned current coupled-world state."""

    physical: PumpStationCoupledPhysicalState
    environment: PumpStationCoupledEnvironment
    resources: PumpStationResourceState
    restrictions: tuple[PumpStationRestriction, ...]
    obligations: tuple[PumpStationObligation, ...]
    work_orders: tuple[PumpStationWorkOrder, ...]
    processes: tuple[PumpStationCoupledProcess, ...]
    evidence: tuple[PumpStationEvidence, ...]
    resource_reservations: tuple[PumpStationPoolReservation, ...]
    assignment: PumpStationDutyAssignment
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
        if len({item.item_id for item in self.backlog}) != len(self.backlog):
            _fail("backlog-identity", "backlog item IDs must be distinct")

    @property
    def state_id(self) -> str:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
            stewardship_state_id,
        )

        return stewardship_state_id(cast(Any, self))

    @property
    def calendar_seconds(self) -> int:
        return self.physical.calendar_seconds

    @property
    def accepted_evidence_ids(self) -> tuple[str, ...]:
        return tuple(
            item.evidence_id
            for item in self.evidence
            if item.accepted_by is not None and (item.health is None or item.health.accepted)
        )

    @property
    def active_restriction_ids(self) -> tuple[str, ...]:
        return tuple(
            item.restriction_id for item in self.restrictions if item.status is PumpStationRestrictionStatus.ACTIVE
        )

    @property
    def active_liability_ids(self) -> tuple[str, ...]:
        obligation_ids = tuple(
            item.obligation_id for item in self.obligations if item.status is not PumpStationObligationStatus.FULFILLED
        )
        outage_ids = tuple(item.episode_id for item in self.outage_episodes if item.status == "open")
        work_ids = tuple(
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
        obligation_ids = tuple(item.obligation_id for item in self.obligations if item.created_sequence > 0)
        work_ids = tuple(item.item_id for item in self.backlog if item.generation_rule_id in {"WG-06", "WG-07"})
        return (*obligation_ids, *work_ids)

    @property
    def discharged_liability_ids(self) -> tuple[str, ...]:
        obligation_ids = tuple(
            item.obligation_id for item in self.obligations if item.status is PumpStationObligationStatus.FULFILLED
        )
        outage_ids = tuple(item.episode_id for item in self.outage_episodes if item.status == "closed")
        work_ids = tuple(
            item.item_id
            for item in self.backlog
            if item.generation_rule_id in {"WG-06", "WG-07"} and item.status is PumpStationBacklogStatus.CLOSED
        )
        return (*obligation_ids, *outage_ids, *work_ids)

    @property
    def terminal_work_item_ids(self) -> tuple[str, ...]:
        terminal = {
            PumpStationBacklogStatus.CLOSED,
            PumpStationBacklogStatus.CANCELLED,
            PumpStationBacklogStatus.SUPERSEDED,
        }
        return tuple(item.item_id for item in self.backlog if item.status in terminal)

    def backlog_item(self, item_id: str) -> PumpStationBacklogItem:
        for item in self.backlog:
            if item.item_id == item_id:
                return item
        _fail("unknown-backlog-item", item_id)

    def restriction(self, kind: PumpStationRestrictionKind, pump_id: str) -> PumpStationRestriction:
        for restriction in reversed(self.restrictions):
            if restriction.kind is kind and restriction.pump_id == pump_id:
                return restriction
        raise LookupError(f"missing restriction {kind.value} for {pump_id}")

    def obligation(self, kind: PumpStationObligationKind, pump_id: str) -> PumpStationObligation:
        for obligation in reversed(self.obligations):
            if obligation.kind is kind and obligation.pump_id == pump_id:
                return obligation
        raise LookupError(f"missing obligation {kind.value} for {pump_id}")

    def work_order_for(self, pump_id: str) -> PumpStationWorkOrder:
        for work_order in reversed(self.work_orders):
            if work_order.pump_id == pump_id:
                return work_order
        raise LookupError(f"missing work order for {pump_id}")

    def process(self, process_id: str) -> PumpStationCoupledProcess:
        for process in self.processes:
            if process.process_id == process_id:
                return process
        raise LookupError(f"missing process {process_id}")

    def latest_inspection(self, pump_id: str) -> PumpStationEvidence:
        return self._latest_evidence(PumpStationEvidenceKind.INSPECTION, pump_id)

    def latest_functional_checks(self, pump_id: str) -> PumpStationEvidence:
        return self._latest_evidence(PumpStationEvidenceKind.FUNCTIONAL_CHECKS, pump_id)

    def _latest_evidence(self, kind: PumpStationEvidenceKind, pump_id: str) -> PumpStationEvidence:
        for evidence in reversed(self.evidence):
            if evidence.kind is kind and evidence.pump_id == pump_id:
                return evidence
        raise LookupError(f"missing {kind.value} evidence for {pump_id}")


@dataclass(frozen=True, slots=True)
class PumpStationOperationsBoundaryReviewRequest:
    review_id: str
    review_kind: str
    pump_id: str
    restriction_or_isolation_permit_id: str
    accepted_evidence_id: str
    requested_outcome: str
    base_state_id: str
    operations_authority_id: str
    reason: str

    @property
    def content_id(self) -> str:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
            stewardship_content_id,
        )

        return stewardship_content_id(self)


@dataclass(frozen=True, slots=True)
class PumpStationProcessOutcomeRequest:
    request_id: str
    authority_id: str
    process_id: str
    outcome: str
    evidence_id: str
    base_state_id: str

    @property
    def content_id(self) -> str:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
            stewardship_content_id,
        )

        return stewardship_content_id(self)


@dataclass(frozen=True, slots=True)
class PumpStationCommonBoundaryRequest:
    request_id: str
    authority_id: str
    boundary_kind: str
    available: bool
    base_state_id: str

    @property
    def content_id(self) -> str:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
            stewardship_content_id,
        )

        return stewardship_content_id(self)


@dataclass(frozen=True, slots=True)
class PumpStationCoupledTreatmentRequest:
    request_id: str
    authority_id: str
    treatment_label: str
    affected_pump_ids: tuple[str, ...]
    obstruction_delta: Decimal
    clearance_loss_delta: Decimal
    base_state_id: str

    @property
    def content_id(self) -> str:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
            stewardship_content_id,
        )

        return stewardship_content_id(self)


type PumpStationRootControl = (
    PumpStationOperationsBoundaryReviewRequest
    | PumpStationProcessOutcomeRequest
    | PumpStationCommonBoundaryRequest
    | PumpStationCoupledTreatmentRequest
)


@dataclass(frozen=True, slots=True)
class PumpStationBoundControlRequest:
    request_id: str
    run_id: str
    episode_id: str
    world_branch_id: str
    base_state_id: str
    base_commit_id: str
    based_on_sequence: int
    control: PumpStationRootControl

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "run_id",
            "episode_id",
            "world_branch_id",
            "base_state_id",
            "base_commit_id",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.based_on_sequence < 0:
            _fail("control-envelope-shape", "based_on_sequence must be non-negative")
        inner_request_id = (
            self.control.review_id
            if isinstance(self.control, PumpStationOperationsBoundaryReviewRequest)
            else self.control.request_id
        )
        if self.request_id != inner_request_id:
            _fail("control-envelope-shape", "outer and inner request identities differ")
        if self.base_state_id != self.control.base_state_id:
            _fail("control-envelope-shape", "outer and inner state bindings differ")

    @property
    def authority_id(self) -> str:
        if isinstance(self.control, PumpStationOperationsBoundaryReviewRequest):
            return self.control.operations_authority_id
        return self.control.authority_id


@dataclass(frozen=True, slots=True)
class PumpStationCoupledTransitionReceipt:
    """Unversioned live result facts for one accepted transition."""

    sequence: int
    transition_id: str
    request_id: str
    action_or_control_kind: str
    actor_action: bool
    authority_outcome: str
    required_authorities: tuple[str, ...]
    authority_decision_detail: str
    permit_ids: tuple[str, ...]
    execution_status: str
    before_state_id: str
    after_state_id: str
    start_calendar_seconds: int
    end_calendar_seconds: int
    target_id: str | None
    backlog_item_id: str | None
    reason: str
    changed_record_ids: tuple[str, ...]
    changed_pool_ids: tuple[str, ...]
    changed_reservation_ids: tuple[str, ...]
    changed_backlog_item_ids: tuple[str, ...]
    generation_record_ids: tuple[str, ...]
    changed_liability_owner_ids: tuple[str, ...]
    operating_interval_id: str | None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            _fail("receipt-shape", "receipt sequence must be positive")
        if self.start_calendar_seconds < 0 or self.end_calendar_seconds < self.start_calendar_seconds:
            _fail("receipt-shape", "receipt time range is invalid")
        for field_name in (
            "transition_id",
            "request_id",
            "action_or_control_kind",
            "authority_outcome",
            "authority_decision_detail",
            "execution_status",
            "before_state_id",
            "after_state_id",
            "reason",
        ):
            _require_text(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class PumpStationCoupledTransition:
    state: PumpStationStewardshipState
    receipt: PumpStationCoupledTransitionReceipt

    def __post_init__(self) -> None:
        if self.state.state_id != self.receipt.after_state_id:
            _fail("transition-integrity", "state and receipt differ")
