# ABOUTME: Runs the complete ASW-8 v4 coupled world through closed actor and host-control transitions.
# ABOUTME: Persists service, resources, work, evidence, and per-pump exposure as immutable state.

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal, NoReturn, cast

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    D_RUNTIME_SECONDS,
    PumpStationBacklogItem,
    PumpStationBacklogStatus,
    PumpStationConsumablePool,
    PumpStationCoupledProcess,
    PumpStationCoupledProcessStatus,
    PumpStationPoolReservation,
    PumpStationPriority,
    PumpStationResourceState,
    PumpStationReusablePool,
    PumpStationWorkGenerationRecord,
    cancel_process_reservations,
    consume_reservation,
    create_asw_8_resource_state,
    generate_work_once,
    release_reservations,
    reserve_process_resources,
    resume_process_reservations,
    retain_consumable_reservations,
    sort_eligible_backlog,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_world import (
    planned_outage_admissible,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PumpStationEvidenceHealth,
    PumpStationEvidenceQuality,
    evidence_quality_at,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    advance_coupled_pump_station,
    coupled_pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpCondition,
    PumpStationCoupledEnvironment,
    PumpStationCoupledModel,
    PumpStationCoupledOperatingInterval,
    PumpStationCoupledPhysicalState,
    PumpStationDutyAssignment,
    PumpStationOperatingDelta,
    PumpStationOutageEpisode,
    PumpStationPumpAvailability,
    PumpStationPumpMode,
    PumpStationServiceRequirement,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V2,
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID,
    create_asw_8_opening_physical_state,
    load_reference_system,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    canonical_stewardship_value,
    stewardship_content_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
    PUMP_STATION_OPERATIONS_REVIEW_VERSION,
    PUMP_STATION_PROCESS_OUTCOME_VERSION,
    PUMP_STATION_STATE_VERSION_V4,
    PumpStationAuthority,
    PumpStationCommonBoundaryRequest,
    PumpStationCoupledTreatmentRequest,
    PumpStationEvidence,
    PumpStationEvidenceKind,
    PumpStationObligation,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
    PumpStationRestriction,
    PumpStationRestrictionKind,
    PumpStationRestrictionStatus,
    PumpStationStewardshipState,
    PumpStationTransitionReceiptV4,
    PumpStationTransitionV4,
    PumpStationWorkOrder,
    PumpStationWorkOrderStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_COUPLED_TREATMENT_VERSION as PUMP_STATION_COUPLED_TREATMENT_VERSION,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    apply_coupled_treatment as _apply_stable_coupled_treatment,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    finish_coupled_transition as _finish_transition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationContinuityCarrier,
    PumpStationCoupledActorView,
    PumpStationCurrentContext,
    PumpStationInformationSet,
    PumpStationObservationHistory,
    bind_information_set,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.time_presentation import (
    PUMP_STATION_TIME_ZONE,
    format_operating_duration,
    pump_station_datetime,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_WORLD_MANIFEST_VERSION_V2 as PUMP_STATION_WORLD_MANIFEST_VERSION_V2,
)

PUMP_STATION_SNAPSHOT_VERSION_V4 = "pump-station-state-snapshot.v4"
PUMP_STATION_ACTOR_PROJECTION_VERSION_V5 = "pump-station-current-state.v5"
PUMP_STATION_ACTOR_VIEW_SCHEMA_V4 = "pump-station.actor-view.v4"
PUMP_STATION_INFORMATION_BOUNDARY_V4 = "pump-station-actor-view.v4"
if TYPE_CHECKING:
    type PumpStationCoupledWorldState = PumpStationStewardshipState[
        PumpStationCoupledPhysicalState,
        PumpStationCoupledEnvironment,
        PumpStationResourceState,
        PumpStationCoupledProcess,
        PumpStationPoolReservation,
    ]

else:
    PumpStationCoupledWorldState = PumpStationStewardshipState


class PumpStationCoupledWorldError(ValueError):
    """Raised when an ASW-8 action or control input fails closed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationCoupledWorldError(code, detail)


PumpStationCoupledTransitionReceipt = PumpStationTransitionReceiptV4
PumpStationCoupledTransition = PumpStationTransitionV4


def _opening_backlog() -> tuple[PumpStationBacklogItem, PumpStationBacklogItem]:
    return (
        PumpStationBacklogItem(
            item_id="backlog-a-verification-001",
            work_type="post_maintenance_verification",
            target_kind="asset",
            target_id="pump-a",
            generation_rule_id="WG-04",
            generation_ordinal=1,
            originating_record_id="initial-a-provisional-return",
            linked_obligation_ids=("obligation-a-verification-001",),
            linked_restriction_ids=("restriction-a-run-in-001",),
            linked_work_order_id="work-order-a-001",
            linked_process_id=None,
            generated_at_calendar_seconds=7_200,
            base_priority=PumpStationPriority.P1,
            effective_priority=PumpStationPriority.P1,
            due_calendar_seconds=64_800,
            due_runtime_clock_kind="pump_total",
            due_runtime_clock_id="pump-a",
            due_runtime_limit_seconds=32_400,
            status=PumpStationBacklogStatus.PLANNED,
            blocked_from_status=None,
            blocked_since_calendar_seconds=None,
            accumulated_blocked_seconds=0,
            closure_rule="verification accepted and Operations review releases run-in",
            closure_evidence_ids=(),
            supersedes_item_id=None,
            superseded_by_item_id=None,
        ),
        PumpStationBacklogItem(
            item_id="backlog-b-clearance-001",
            work_type="obstruction_clearance",
            target_kind="asset",
            target_id="pump-b",
            generation_rule_id="WG-02",
            generation_ordinal=1,
            originating_record_id="initial-b-inspection-accepted",
            linked_obligation_ids=(),
            linked_restriction_ids=("restriction-b-isolated-001",),
            linked_work_order_id="work-order-b-001",
            linked_process_id=None,
            generated_at_calendar_seconds=21_600,
            base_priority=PumpStationPriority.P1,
            effective_priority=PumpStationPriority.P1,
            due_calendar_seconds=64_800,
            due_runtime_clock_kind=None,
            due_runtime_clock_id=None,
            due_runtime_limit_seconds=None,
            status=PumpStationBacklogStatus.PLANNED,
            blocked_from_status=None,
            blocked_since_calendar_seconds=None,
            accumulated_blocked_seconds=0,
            closure_rule="clearance completes and functional check is generated",
            closure_evidence_ids=(),
            supersedes_item_id=None,
            superseded_by_item_id=None,
        ),
    )


def _accepted_evidence_record(
    *,
    evidence_id: str,
    kind: PumpStationEvidenceKind,
    pump_id: str,
    created_at_seconds: int,
    produced_by: PumpStationAuthority,
    accepted_by: PumpStationAuthority,
    passed: bool | None = None,
) -> PumpStationEvidence:
    return PumpStationEvidence(
        evidence_id=evidence_id,
        kind=kind,
        pump_id=pump_id,
        created_at_seconds=created_at_seconds,
        produced_by=produced_by,
        accepted_by=accepted_by,
        passed=passed,
        health=PumpStationEvidenceHealth(
            observed_at_seconds=created_at_seconds,
            produced_at_seconds=created_at_seconds,
            available_at_seconds=created_at_seconds,
            source_id=f"source-{evidence_id}",
            component_scope=(pump_id,),
            baseline_id="asw-8-rs1-opening-baseline",
            operating_regime_id="asw-8-rs1-declared-regime",
            accepted=True,
            quality=PumpStationEvidenceQuality.CURRENT,
        ),
    )


def create_asw_8_world_state() -> PumpStationCoupledWorldState:
    """Construct the exact descriptor-bound ASW-8 opening state."""
    system = load_reference_system()
    state = cast(
        PumpStationCoupledWorldState,
        PumpStationStewardshipState(
            physical=create_asw_8_opening_physical_state(),
            environment=PumpStationCoupledEnvironment(
                inflow_m3_s=Decimal("0.0155"),
                wet_well_level_m=Decimal("1.65"),
            ),
            sequence=0,
            resources=create_asw_8_resource_state(),
            restrictions=(
                PumpStationRestriction(
                    restriction_id="restriction-a-run-in-001",
                    kind=PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN,
                    pump_id="pump-a",
                    status=PumpStationRestrictionStatus.ACTIVE,
                    created_sequence=0,
                ),
                PumpStationRestriction(
                    restriction_id="restriction-b-isolated-001",
                    kind=PumpStationRestrictionKind.NO_INTERVENTION,
                    pump_id="pump-b",
                    status=PumpStationRestrictionStatus.ACTIVE,
                    created_sequence=0,
                    evidence_id="initial-b-inspection-accepted",
                ),
            ),
            obligations=(
                PumpStationObligation(
                    obligation_id="obligation-a-verification-001",
                    kind=PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
                    pump_id="pump-a",
                    status=PumpStationObligationStatus.ACTIVE,
                    originating_proposal_id="initial-a-provisional-return",
                    responsible_authority=PumpStationAuthority.VERIFICATION,
                    linked_restriction_id="restriction-a-run-in-001",
                    due_calendar_seconds=64_800,
                    due_runtime_seconds=32_400,
                    created_sequence=0,
                ),
            ),
            work_orders=(
                PumpStationWorkOrder(
                    work_order_id="work-order-a-001",
                    pump_id="pump-a",
                    status=PumpStationWorkOrderStatus.OPEN,
                    created_sequence=0,
                ),
                PumpStationWorkOrder(
                    work_order_id="work-order-b-001",
                    pump_id="pump-b",
                    status=PumpStationWorkOrderStatus.OPEN,
                    created_sequence=0,
                ),
            ),
            processes=(),
            evidence=(
                _accepted_evidence_record(
                    evidence_id="initial-b-inspection-accepted",
                    kind=PumpStationEvidenceKind.INSPECTION,
                    pump_id="pump-b",
                    created_at_seconds=21_600,
                    produced_by=PumpStationAuthority.MAINTENANCE,
                    accepted_by=PumpStationAuthority.MAINTENANCE,
                ),
                _accepted_evidence_record(
                    evidence_id="initial-c-assurance-accepted",
                    kind=PumpStationEvidenceKind.CONDITION_CHECK,
                    pump_id="pump-c",
                    created_at_seconds=21_600,
                    produced_by=PumpStationAuthority.ENGINEERING,
                    accepted_by=PumpStationAuthority.OPERATIONS,
                    passed=True,
                ),
            ),
            scheduled_events=(),
            state_version=PUMP_STATION_STATE_VERSION_V4,
            assignment=PumpStationDutyAssignment(
                assignment_id="assignment-opening-c",
                ordered_pump_ids=("pump-c",),
                active=True,
                source_need_id="opening-normal-service",
                effective_transition_id="initial-state",
                required_service_scu=1,
                assigned_service_scu=1,
                unserved_service_scu=0,
                decision_detail="accepted initial assignment",
            ),
            service_schedule=(
                PumpStationServiceRequirement(21_600, 64_800, 1),
                PumpStationServiceRequirement(64_800, 93_600, 2),
                PumpStationServiceRequirement(93_600, 226_800, 1),
            ),
            baseline_schedule=(
                (21_600, 64_800, ("pump-c",)),
                (64_800, 93_600, ("pump-a", "pump-b")),
                (93_600, 226_800, ("pump-a",)),
            ),
            disclosed_through_calendar_seconds=226_800,
            resource_reservations=(),
            backlog=_opening_backlog(),
            generation_records=(),
            outage_episodes=(
                PumpStationOutageEpisode(
                    episode_id="outage-b-001",
                    unavailable_baseline_pump_id="pump-b",
                    source_record_id="initial-b-inspection-accepted",
                    opening_transition_id="initial-state",
                    closing_transition_id=None,
                    status="open",
                ),
            ),
            operating_intervals=(),
            collateral_runtime=(("outage-b-001", "pump-c", 0),),
            pending_start_pump_ids=(),
            event_effect_ids=(),
        ),
    )
    expected = canonical_stewardship_value(system.opening_state, record_profile="v4")
    if _opening_state_specification_value(state) != expected:
        _fail("opening-state-binding", "constructed state differs from its specification")
    return state


def _opening_state_specification_value(
    state: PumpStationCoupledWorldState,
) -> dict[str, object]:
    reusable = tuple(pool for pool in state.resources.pools if isinstance(pool, PumpStationReusablePool))
    consumable = tuple(pool for pool in state.resources.pools if isinstance(pool, PumpStationConsumablePool))
    return {
        "accepted_evidence": [
            {
                "accepted_by": cast(PumpStationAuthority, item.accepted_by).value,
                "evidence_id": item.evidence_id,
                "kind": item.kind.value,
                "operating_regime_id": cast(PumpStationEvidenceHealth, item.health).operating_regime_id,
                "pump_id": item.pump_id,
                "quality": cast(PumpStationEvidenceHealth, item.health).quality.value,
                "source_id": cast(PumpStationEvidenceHealth, item.health).source_id,
            }
            for item in state.evidence
        ],
        "assignment": {
            "assigned_service_scu": state.assignment.assigned_service_scu,
            "assignment_id": state.assignment.assignment_id,
            "decision_detail": state.assignment.decision_detail,
            "ordered_pump_ids": list(state.assignment.ordered_pump_ids),
            "required_service_scu": state.assignment.required_service_scu,
            "unserved_service_scu": state.assignment.unserved_service_scu,
        },
        "backlog": [
            {
                "base_priority": item.base_priority.value,
                "due_calendar_seconds": item.due_calendar_seconds,
                "due_runtime_limit_seconds": item.due_runtime_limit_seconds,
                "generated_at_calendar_seconds": item.generated_at_calendar_seconds,
                "generation_rule_id": item.generation_rule_id,
                "item_id": item.item_id,
                "status": item.status.value,
                "target_id": item.target_id,
                "work_type": item.work_type,
            }
            for item in state.backlog
        ],
        "calendar_seconds": state.calendar_seconds,
        "common_boundary": {
            "discharge_available": state.physical.common_boundary.discharge_available,
            "power_available": state.physical.common_boundary.power_available,
        },
        "environment": {
            "inflow_m3_s": str(state.environment.inflow_m3_s),
            "wet_well_level_m": str(state.environment.wet_well_level_m),
        },
        "liability_owner_ids": list(state.active_liability_ids),
        "outage_episodes": [
            {
                "episode_id": item.episode_id,
                "source_record_id": item.source_record_id,
                "status": item.status,
                "unavailable_baseline_pump_id": item.unavailable_baseline_pump_id,
            }
            for item in state.outage_episodes
        ],
        "profile_id": REFERENCE_PROFILE_V2,
        "pump_boundaries": {
            item.pump_id: {
                "mode": item.mode.value,
                "source_id": item.source_permit_or_evidence_id,
            }
            for item in state.physical.pump_boundaries
        },
        "pumps": {
            item.pump_id: {
                "clearance_loss": str(item.condition.clearance_loss),
                "completed_starts": item.exposure.completed_starts,
                "obstruction": str(item.condition.obstruction),
                "runtime_seconds": item.exposure.runtime_seconds,
            }
            for item in state.physical.pumps
        },
        "required_actions": [
            {
                "due_calendar_seconds": item.due_calendar_seconds,
                "due_runtime_seconds": item.due_runtime_seconds,
                "kind": item.kind.value,
                "obligation_id": item.obligation_id,
                "pump_id": item.pump_id,
                "responsible_authority": item.responsible_authority.value,
                "status": item.status.value,
            }
            for item in state.obligations
        ],
        "resource_state": {
            "consumable_pools": [
                {
                    "free": item.free,
                    "on_hand": item.on_hand,
                    "pool_id": item.pool_id,
                    "reserved": item.reserved,
                }
                for item in consumable
            ],
            "reusable_pools": [
                {
                    "availability_intervals": [
                        {
                            "end_calendar_seconds": interval.end_calendar_seconds,
                            "start_calendar_seconds": interval.start_calendar_seconds,
                        }
                        for interval in item.availability_intervals
                    ],
                    "capacity": item.capacity,
                    "free": item.free,
                    "pool_id": item.pool_id,
                    "reserved": item.reserved,
                    "unavailable": item.unavailable,
                }
                for item in reusable
            ],
        },
        "restrictions": [
            {
                "kind": item.kind.value,
                "pump_id": item.pump_id,
                "restriction_id": item.restriction_id,
                "status": item.status.value,
            }
            for item in state.restrictions
        ],
        "schema_id": PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID,
        "service_running_pump_ids": list(state.physical.service_running_pump_ids),
        "specification_id": PUMP_STATION_ASW_8_INITIAL_STATE_SPECIFICATION_ID,
        "test_running_pump_ids": list(state.physical.test_running_pump_ids),
        "work_orders": [
            {
                "pump_id": item.pump_id,
                "status": item.status.value,
                "work_order_id": item.work_order_id,
            }
            for item in state.work_orders
        ],
    }


def _model() -> PumpStationCoupledModel:
    return coupled_pump_station_model_from_package(load_reference_package(profile_id=REFERENCE_PROFILE_V2))


def _service_requirement(state: PumpStationCoupledWorldState, at_seconds: int) -> int:
    for requirement in state.service_schedule:
        if requirement.start_calendar_seconds <= at_seconds < requirement.end_calendar_seconds:
            return requirement.required_service_scu
    _fail("service-schedule", f"no requirement at {at_seconds}")


def _baseline_assignment(state: PumpStationCoupledWorldState, at_seconds: int) -> tuple[str, ...]:
    for start, end, pumps in state.baseline_schedule:
        if start <= at_seconds < end:
            return pumps
    _fail("baseline-schedule", f"no baseline at {at_seconds}")


def _selected_service_running(
    state: PumpStationCoupledWorldState,
    assignment: tuple[str, ...] | None = None,
    required_scu: int | None = None,
) -> tuple[str, ...]:
    if assignment is None and not state.assignment.active:
        return ()
    selected_assignment = assignment or state.assignment.ordered_pump_ids
    required = required_scu or _service_requirement(state, state.calendar_seconds)
    eligible = tuple(pump_id for pump_id in selected_assignment if state.physical.availability(pump_id).run_eligible)
    return eligible[:required]


def _with_physical_running_sets(
    state: PumpStationCoupledWorldState,
    *,
    service: tuple[str, ...],
    test: tuple[str, ...] | None = None,
) -> PumpStationCoupledWorldState:
    previous = set(state.physical.service_running_pump_ids) | set(state.physical.test_running_pump_ids)
    selected_test = state.physical.test_running_pump_ids if test is None else test
    current = set(service) | set(selected_test)
    pending = tuple(sorted(set(state.pending_start_pump_ids) | (current - previous)))
    return replace(
        state,
        physical=replace(
            state.physical,
            service_running_pump_ids=service,
            test_running_pump_ids=selected_test,
        ),
        pending_start_pump_ids=pending,
    )


def _replace_backlog_item(
    state: PumpStationCoupledWorldState,
    item: PumpStationBacklogItem,
) -> PumpStationCoupledWorldState:
    state.backlog_item(item.item_id)
    return replace(
        state,
        backlog=tuple(item if value.item_id == item.item_id else value for value in state.backlog),
    )


def _start_process(
    state: PumpStationCoupledWorldState,
    *,
    kind: str,
    target_id: str,
    backlog_item_id: str,
    duration_seconds: int,
    pool_ids: tuple[str, ...],
) -> PumpStationCoupledWorldState:
    _require_field_process_admissible(
        state,
        process_kind=kind,
        target_id=target_id,
        duration_seconds=duration_seconds,
    )
    item = state.backlog_item(backlog_item_id)
    if item.target_id != target_id or item.status not in {
        PumpStationBacklogStatus.OPEN,
        PumpStationBacklogStatus.PLANNED,
    }:
        _fail("backlog-binding", backlog_item_id)
    if any(process.status is PumpStationCoupledProcessStatus.ACTIVE for process in state.processes):
        _fail("process-conflict", "the shared work lane already has an active process")
    process_id = f"process-{kind}-{target_id}-{state.sequence + 1}"
    resources, reservations = reserve_process_resources(
        state.resources,
        state.resource_reservations,
        process_id=process_id,
        target_id=target_id,
        pool_ids=pool_ids,
        now_calendar_seconds=state.calendar_seconds,
        duration_seconds=duration_seconds,
    )
    process = PumpStationCoupledProcess(
        process_id=process_id,
        kind=kind,
        target_id=target_id,
        backlog_item_id=backlog_item_id,
        started_at_calendar_seconds=state.calendar_seconds,
        due_at_calendar_seconds=state.calendar_seconds + duration_seconds,
        remaining_duration_seconds=duration_seconds,
        required_pool_ids=pool_ids,
        status=PumpStationCoupledProcessStatus.ACTIVE,
    )
    return replace(
        _replace_backlog_item(
            state,
            replace(
                item,
                status=PumpStationBacklogStatus.IN_PROGRESS,
                linked_process_id=process_id,
            ),
        ),
        resources=resources,
        resource_reservations=reservations,
        processes=(*state.processes, process),
    )


def _require_field_process_admissible(
    state: PumpStationCoupledWorldState,
    *,
    process_kind: str,
    target_id: str,
    duration_seconds: int,
) -> None:
    if not state.physical.common_boundary.available:
        _fail("field-process-boundary", "common operating boundary is unavailable")
    isolated_other_targets = tuple(
        boundary.pump_id
        for boundary in state.physical.pump_boundaries
        if boundary.pump_id != target_id and boundary.mode is PumpStationPumpMode.ISOLATED_FOR_WORK
    )
    if process_kind in {"inspection", "obstruction_clearance"} and isolated_other_targets:
        _fail("field-process-isolation", isolated_other_targets[0])
    if not planned_outage_admissible(
        state.physical,
        target_pump_id=target_id,
        start_calendar_seconds=state.calendar_seconds,
        completion_calendar_seconds=state.calendar_seconds + duration_seconds,
        visible_service_schedule=tuple(
            requirement
            for requirement in state.service_schedule
            if requirement.end_calendar_seconds > state.calendar_seconds
        ),
        disclosed_through_calendar_seconds=state.disclosed_through_calendar_seconds,
    ):
        _fail(
            "planned-outage-capacity",
            f"assured non-target service does not cover {target_id} through completion",
        )


def _generated_item(
    *,
    rule_id: str,
    source_transition_id: str,
    target_kind: str,
    target_id: str,
    ordinal: int,
    work_type: str,
    generated_at: int,
    priority: PumpStationPriority,
    due_calendar_seconds: int | None,
    due_runtime_kind: str | None = None,
    due_runtime_id: str | None = None,
    due_runtime_limit: int | None = None,
    obligation_ids: tuple[str, ...] = (),
    restriction_ids: tuple[str, ...] = (),
    closure_rule: str,
) -> tuple[PumpStationWorkGenerationRecord, PumpStationBacklogItem]:
    stable = stewardship_content_id(
        (rule_id, source_transition_id, target_kind, target_id, ordinal),
        record_profile="v4",
    )[:16]
    item_id = f"backlog-{rule_id.lower()}-{target_id}-{ordinal}-{stable}"
    return (
        PumpStationWorkGenerationRecord(
            rule_id=rule_id,
            source_transition_id=source_transition_id,
            target_kind=target_kind,
            target_id=target_id,
            generation_ordinal=ordinal,
            backlog_item_id=item_id,
        ),
        PumpStationBacklogItem(
            item_id=item_id,
            work_type=work_type,
            target_kind=target_kind,
            target_id=target_id,
            generation_rule_id=rule_id,
            generation_ordinal=ordinal,
            originating_record_id=source_transition_id,
            linked_obligation_ids=obligation_ids,
            linked_restriction_ids=restriction_ids,
            linked_work_order_id=None,
            linked_process_id=None,
            generated_at_calendar_seconds=generated_at,
            base_priority=priority,
            effective_priority=priority,
            due_calendar_seconds=due_calendar_seconds,
            due_runtime_clock_kind=due_runtime_kind,
            due_runtime_clock_id=due_runtime_id,
            due_runtime_limit_seconds=due_runtime_limit,
            status=PumpStationBacklogStatus.PLANNED,
            blocked_from_status=None,
            blocked_since_calendar_seconds=None,
            accumulated_blocked_seconds=0,
            closure_rule=closure_rule,
            closure_evidence_ids=(),
            supersedes_item_id=None,
            superseded_by_item_id=None,
        ),
    )


def _add_generated_work(
    state: PumpStationCoupledWorldState,
    generation: PumpStationWorkGenerationRecord,
    item: PumpStationBacklogItem,
) -> PumpStationCoupledWorldState:
    result = generate_work_once(
        state.generation_records,
        state.backlog,
        generation,
        item,
    )
    return replace(
        state,
        generation_records=result.records,
        backlog=result.backlog,
    )


def _collateral_runtime(
    state: PumpStationCoupledWorldState,
    episode_id: str,
    pump_id: str,
) -> int:
    for episode, pump, seconds in state.collateral_runtime:
        if episode == episode_id and pump == pump_id:
            return seconds
    return 0


def _runtime_clock_values(
    state: PumpStationCoupledWorldState,
) -> dict[tuple[str, str], int]:
    values = {("pump_total", pump.pump_id): pump.exposure.runtime_seconds for pump in state.physical.pumps}
    values.update(
        {
            ("outage_episode_collateral", f"{episode_id}:{pump_id}"): seconds
            for episode_id, pump_id, seconds in state.collateral_runtime
        }
    )
    return values


def _runtime_clock_accrues(
    state: PumpStationCoupledWorldState,
    *,
    clock_kind: str,
    clock_id: str,
) -> bool:
    running = set(state.physical.service_running_pump_ids) | set(state.physical.test_running_pump_ids)
    if clock_kind == "pump_total":
        return clock_id in running
    if clock_kind != "outage_episode_collateral" or ":" not in clock_id:
        return False
    episode_id, pump_id = clock_id.rsplit(":", 1)
    if pump_id not in state.physical.service_running_pump_ids:
        return False
    matching = tuple(
        episode for episode in state.outage_episodes if episode.episode_id == episode_id and episode.status == "open"
    )
    if len(matching) != 1:
        return False
    return matching[0].unavailable_baseline_pump_id in _baseline_assignment(
        state,
        state.calendar_seconds,
    )


def _runtime_boundary_candidates(
    state: PumpStationCoupledWorldState,
) -> tuple[tuple[int, str, str], ...]:
    clocks = _runtime_clock_values(state)
    candidates: list[tuple[int, str, str]] = []
    active_statuses = {
        PumpStationBacklogStatus.OPEN,
        PumpStationBacklogStatus.PLANNED,
        PumpStationBacklogStatus.IN_PROGRESS,
        PumpStationBacklogStatus.BLOCKED,
    }
    for item in state.backlog:
        if (
            item.status not in active_statuses
            or item.due_runtime_clock_kind is None
            or item.due_runtime_clock_id is None
            or item.due_runtime_limit_seconds is None
            or not _runtime_clock_accrues(
                state,
                clock_kind=item.due_runtime_clock_kind,
                clock_id=item.due_runtime_clock_id,
            )
        ):
            continue
        current = clocks.get((item.due_runtime_clock_kind, item.due_runtime_clock_id))
        if current is None:
            continue
        boundaries = (
            (item.due_runtime_limit_seconds - 2 * D_RUNTIME_SECONDS, "p2"),
            (item.due_runtime_limit_seconds - D_RUNTIME_SECONDS, "p1"),
            (item.due_runtime_limit_seconds, "due"),
        )
        candidates.extend(
            (
                state.calendar_seconds + threshold - current,
                item.item_id,
                label,
            )
            for threshold, label in boundaries
            if threshold > current
        )
    return tuple(candidates)


def _runtime_boundary_effect_ids(
    state: PumpStationCoupledWorldState,
) -> tuple[str, ...]:
    clocks = _runtime_clock_values(state)
    effects: list[str] = []
    for item in state.backlog:
        if (
            item.due_runtime_clock_kind is None
            or item.due_runtime_clock_id is None
            or item.due_runtime_limit_seconds is None
        ):
            continue
        current = clocks.get((item.due_runtime_clock_kind, item.due_runtime_clock_id))
        if current is None:
            continue
        boundaries = (
            (item.due_runtime_limit_seconds - 2 * D_RUNTIME_SECONDS, "p2"),
            (item.due_runtime_limit_seconds - D_RUNTIME_SECONDS, "p1"),
            (item.due_runtime_limit_seconds, "due"),
        )
        for threshold, label in boundaries:
            effect_id = f"backlog-runtime-boundary-{item.item_id}-{label}"
            if threshold == current and effect_id not in state.event_effect_ids:
                effects.append(effect_id)
    return tuple(effects)


def _advance_physical(
    model: PumpStationCoupledModel,
    state: PumpStationCoupledWorldState,
    end_seconds: int,
    transition_id: str,
) -> PumpStationCoupledWorldState:
    elapsed = end_seconds - state.calendar_seconds
    if elapsed <= 0:
        _fail("time-order", str(end_seconds))
    baseline = _baseline_assignment(state, state.calendar_seconds)
    deltas: list[PumpStationOperatingDelta] = []
    for pump in state.physical.pumps:
        service_runtime = elapsed if pump.pump_id in state.physical.service_running_pump_ids else 0
        test_runtime = elapsed if pump.pump_id in state.physical.test_running_pump_ids else 0
        attributed_episode = (
            "outage-b-001"
            if pump.pump_id == "pump-c"
            and "pump-b" in baseline
            and service_runtime
            and any(
                episode.episode_id == "outage-b-001" and episode.status == "open" for episode in state.outage_episodes
            )
            else None
        )
        deltas.append(
            PumpStationOperatingDelta(
                pump_id=pump.pump_id,
                service_runtime_seconds=service_runtime,
                test_runtime_seconds=test_runtime,
                attributed_outage_episode_id=attributed_episode,
                start_added=int(pump.pump_id in state.pending_start_pump_ids),
            )
        )
    interval = PumpStationCoupledOperatingInterval(
        start_calendar_seconds=state.calendar_seconds,
        end_calendar_seconds=end_seconds,
        required_service_scu=_service_requirement(state, state.calendar_seconds),
        baseline_assignment_pump_ids=baseline,
        actual_assignment_pump_ids=state.assignment.ordered_pump_ids,
        service_running_pump_ids=state.physical.service_running_pump_ids,
        test_running_pump_ids=state.physical.test_running_pump_ids,
        pump_deltas=cast(
            tuple[PumpStationOperatingDelta, PumpStationOperatingDelta, PumpStationOperatingDelta],
            tuple(deltas),
        ),
    )
    result = advance_coupled_pump_station(model, state.physical, interval)
    collateral = list(state.collateral_runtime)
    for delta in result.operating_interval.pump_deltas:
        if delta.attributed_outage_episode_id is None:
            continue
        key = (delta.attributed_outage_episode_id, delta.pump_id)
        prior = _collateral_runtime(state, *key)
        collateral = [row for row in collateral if row[:2] != key]
        collateral.append((*key, prior + delta.collateral_runtime_seconds))
    updated = replace(
        state,
        physical=result.state,
        operating_intervals=(*state.operating_intervals, result.operating_interval),
        collateral_runtime=tuple(sorted(collateral)),
        pending_start_pump_ids=(),
    )
    if _collateral_runtime(updated, "outage-b-001", "pump-c") >= 28_800 and not any(
        item.generation_rule_id == "WG-07" and item.target_id == "pump-c" for item in updated.backlog
    ):
        generation, item = _generated_item(
            rule_id="WG-07",
            source_transition_id=transition_id,
            target_kind="asset",
            target_id="pump-c",
            ordinal=1,
            work_type="collateral_duty_inspection",
            generated_at=end_seconds,
            priority=PumpStationPriority.P2,
            due_calendar_seconds=end_seconds + 57_600,
            due_runtime_kind="outage_episode_collateral",
            due_runtime_id="outage-b-001:pump-c",
            due_runtime_limit=86_400,
            closure_rule="accepted inspection for Pump C",
        )
        updated = _add_generated_work(updated, generation, item)
    return updated


_STATIC_EVENT_TIMES = (61_200, 64_800, 93_600, 100_800, 108_000, 122_400, 151_200, 165_600, 194_400, 226_800)


def _next_event_time(state: PumpStationCoupledWorldState) -> int:
    candidates = [value for value in _STATIC_EVENT_TIMES if value > state.calendar_seconds]
    candidates.extend(
        process.due_at_calendar_seconds
        for process in state.processes
        if process.status is PumpStationCoupledProcessStatus.ACTIVE
        and process.due_at_calendar_seconds > state.calendar_seconds
    )
    candidates.extend(value[0] for value in _runtime_boundary_candidates(state))
    if not candidates:
        _fail("no-next-event", str(state.calendar_seconds))
    return min(candidates)


def _set_reusable_availability(
    state: PumpStationCoupledWorldState,
    *,
    available: bool,
) -> PumpStationCoupledWorldState:
    resources = state.resources
    for pool in resources.pools:
        if not isinstance(pool, PumpStationReusablePool):
            continue
        if pool.reserved:
            _fail("resource-withdrawal", f"{pool.pool_id} remains reserved")
        resources = resources.with_pool(
            replace(
                pool,
                free=pool.capacity if available else 0,
                unavailable=0 if available else pool.capacity,
            )
        )
    return replace(state, resources=resources)


def _suspend_process(
    state: PumpStationCoupledWorldState,
    process: PumpStationCoupledProcess,
) -> PumpStationCoupledWorldState:
    """Suspend one active process before a safety or resource-withdrawal event."""
    if process.status is not PumpStationCoupledProcessStatus.ACTIVE:
        return state
    resources, reservations = retain_consumable_reservations(
        state.resources,
        state.resource_reservations,
        now_calendar_seconds=state.calendar_seconds,
    )
    item = state.backlog_item(process.backlog_item_id)
    blocked = replace(
        item,
        status=PumpStationBacklogStatus.BLOCKED,
        blocked_from_status=item.status,
        blocked_since_calendar_seconds=state.calendar_seconds,
    )
    suspended = replace(
        process,
        status=PumpStationCoupledProcessStatus.SUSPENDED,
        remaining_duration_seconds=max(
            0,
            process.due_at_calendar_seconds - state.calendar_seconds,
        ),
    )
    test_running = tuple(pump_id for pump_id in state.physical.test_running_pump_ids if pump_id != process.target_id)
    return replace(
        _replace_backlog_item(state, blocked),
        physical=replace(state.physical, test_running_pump_ids=test_running),
        resources=resources,
        resource_reservations=reservations,
        processes=tuple(suspended if value.process_id == process.process_id else value for value in state.processes),
    )


def _complete_process(
    state: PumpStationCoupledWorldState,
    process: PumpStationCoupledProcess,
    transition_id: str,
) -> PumpStationCoupledWorldState:
    resources = state.resources
    reservations = state.resource_reservations
    item = state.backlog_item(process.backlog_item_id)
    physical = state.physical
    evidence = state.evidence
    restrictions = state.restrictions
    updated = state
    if process.kind == "obstruction_clearance":
        resources, reservations = consume_reservation(
            resources,
            reservations,
            pool_id="obstruction-clearance-kit",
            process_id=process.process_id,
            now_calendar_seconds=state.calendar_seconds,
        )
        pump = physical.pump(process.target_id)
        cleared = PumpCondition(
            obstruction=max(Decimal("0.02"), Decimal("0.15") * pump.condition.obstruction),
            clearance_loss=pump.condition.clearance_loss,
        )
        physical = replace(
            physical,
            pumps=cast(
                tuple[Any, Any, Any],
                tuple(
                    replace(value, condition=cleared) if value.pump_id == pump.pump_id else value
                    for value in physical.pumps
                ),
            ),
        ).with_boundary_mode(process.target_id, PumpStationPumpMode.TEST_ONLY, transition_id)
        target_label = process.target_id.removeprefix("pump-")
        restrictions = tuple(
            replace(value, status=PumpStationRestrictionStatus.LIFTED)
            if value.pump_id == process.target_id
            and value.status is PumpStationRestrictionStatus.ACTIVE
            and value.kind is PumpStationRestrictionKind.NO_INTERVENTION
            else value
            for value in restrictions
        )
        evidence_id = f"evidence-{target_label}-clearance-complete-001"
        evidence = (
            *evidence,
            _accepted_evidence_record(
                evidence_id=evidence_id,
                kind=PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
                pump_id=process.target_id,
                created_at_seconds=state.calendar_seconds,
                produced_by=PumpStationAuthority.MAINTENANCE,
                accepted_by=PumpStationAuthority.MAINTENANCE,
                passed=True,
            ),
        )
        item = replace(
            item,
            status=PumpStationBacklogStatus.CLOSED,
            closure_evidence_ids=(evidence_id,),
        )
        generation, functional = _generated_item(
            rule_id="WG-03",
            source_transition_id=transition_id,
            target_kind="asset",
            target_id=process.target_id,
            ordinal=1,
            work_type="minimum_functional_check",
            generated_at=state.calendar_seconds,
            priority=PumpStationPriority.P1,
            due_calendar_seconds=state.calendar_seconds + 3_600,
            closure_rule="accepted functional-check evidence",
        )
        updated = _add_generated_work(updated, generation, functional)
        generation, replenishment = _generated_item(
            rule_id="WG-06",
            source_transition_id=transition_id,
            target_kind="resource_pool",
            target_id="obstruction-clearance-kit",
            ordinal=1,
            work_type="replenish_clearance_kit",
            generated_at=state.calendar_seconds,
            priority=PumpStationPriority.P2,
            due_calendar_seconds=state.calendar_seconds + 1_209_600,
            closure_rule="declared stock arrival is recorded",
        )
        updated = _add_generated_work(updated, generation, replenishment)
    elif process.kind == "functional_check":
        physical = replace(physical, test_running_pump_ids=())
        evidence_id = f"evidence-{process.target_id.removeprefix('pump-')}-functional-check-pass-001"
        evidence = (
            *evidence,
            _accepted_evidence_record(
                evidence_id=evidence_id,
                kind=PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
                pump_id=process.target_id,
                created_at_seconds=state.calendar_seconds,
                produced_by=PumpStationAuthority.MAINTENANCE,
                accepted_by=PumpStationAuthority.OPERATIONS,
                passed=True,
            ),
        )
        item = replace(
            item,
            status=PumpStationBacklogStatus.CLOSED,
            closure_evidence_ids=(evidence_id,),
        )
    elif process.kind == "post_maintenance_verification":
        evidence_id = f"evidence-{process.target_id}-verification-pass-001"
        evidence = (
            *evidence,
            _accepted_evidence_record(
                evidence_id=evidence_id,
                kind=PumpStationEvidenceKind.POST_MAINTENANCE_VERIFICATION,
                pump_id=process.target_id,
                created_at_seconds=state.calendar_seconds,
                produced_by=PumpStationAuthority.VERIFICATION,
                accepted_by=PumpStationAuthority.VERIFICATION,
                passed=True,
            ),
        )
        item = replace(
            item,
            status=PumpStationBacklogStatus.COMPLETED,
            closure_evidence_ids=(evidence_id,),
        )
    elif process.kind == "inspection":
        evidence_id = f"evidence-{process.target_id.removeprefix('pump-')}-inspection-no-finding-001"
        evidence = (
            *evidence,
            _accepted_evidence_record(
                evidence_id=evidence_id,
                kind=PumpStationEvidenceKind.INSPECTION,
                pump_id=process.target_id,
                created_at_seconds=state.calendar_seconds,
                produced_by=PumpStationAuthority.MAINTENANCE,
                accepted_by=PumpStationAuthority.MAINTENANCE,
                passed=True,
            ),
        )
        item = replace(
            item,
            status=PumpStationBacklogStatus.CLOSED,
            closure_evidence_ids=(evidence_id,),
        )
    else:
        _fail("process-kind", process.kind)
    resources, reservations = release_reservations(
        resources,
        reservations,
        process_id=process.process_id,
        now_calendar_seconds=state.calendar_seconds,
    )
    completed_process = replace(
        process,
        status=PumpStationCoupledProcessStatus.COMPLETED,
        remaining_duration_seconds=0,
    )
    return replace(
        _replace_backlog_item(updated, item),
        physical=physical,
        resources=resources,
        resource_reservations=reservations,
        processes=tuple(
            completed_process if value.process_id == process.process_id else value for value in updated.processes
        ),
        evidence=evidence,
        restrictions=restrictions,
    )


def _apply_event_effects(
    state: PumpStationCoupledWorldState,
    *,
    event_time: int,
    transition_id: str,
) -> PumpStationCoupledWorldState:
    updated = state
    effect_ids = list(updated.event_effect_ids)
    effect_ids.extend(_runtime_boundary_effect_ids(state))
    if event_time in {61_200, 165_600, 226_800}:
        for process in tuple(updated.processes):
            if process.status is PumpStationCoupledProcessStatus.ACTIVE:
                updated = _suspend_process(updated, process)
                effect_ids.append(f"process-suspended-{process.process_id}-{event_time}")
        updated = _set_reusable_availability(updated, available=False)
        effect_ids.append(f"resource-window-close-{event_time}")
    if event_time in {108_000, 194_400}:
        updated = _set_reusable_availability(updated, available=True)
        effect_ids.append(f"resource-window-open-{event_time}")
    if event_time == 64_800:
        service = _selected_service_running(updated, required_scu=2)
        updated = _with_physical_running_sets(updated, service=service)
        effect_ids.append("service-peak-start")
    if event_time == 93_600:
        service = _selected_service_running(updated, required_scu=1)
        updated = _with_physical_running_sets(updated, service=service)
        effect_ids.append("service-peak-end")
    if event_time == 100_800:
        effect_ids.append("document-review-point-c-001")
    if event_time == 122_400:
        effect_ids.append("backlog-priority-c-p1")
    if event_time == 151_200:
        effect_ids.append("backlog-c-due")
    updated = replace(updated, event_effect_ids=tuple(effect_ids))
    due_processes = tuple(
        process
        for process in updated.processes
        if process.status is PumpStationCoupledProcessStatus.ACTIVE and process.due_at_calendar_seconds == event_time
    )
    for process in due_processes:
        updated = _complete_process(updated, process, transition_id)
    return updated


def pump_station_root_control_operations(
    state: PumpStationCoupledWorldState | None,
    *,
    authority_id: str,
    process_id: str | None = None,
) -> tuple[Literal["operations_review", "process_outcome", "common_boundary"], ...]:
    """Return root controls permitted by current pump-task authority semantics."""
    operations: list[Literal["operations_review", "process_outcome", "common_boundary"]] = []
    if authority_id == "operations-controller":
        operations.extend(("operations_review", "common_boundary"))
    if state is None:
        return tuple(operations)
    process_authorities = {
        "functional_check": "maintenance-controller",
        "post_maintenance_verification": "verification-engineer-01",
    }
    if any(
        process.status is PumpStationCoupledProcessStatus.ACTIVE
        and (process_id is None or process.process_id == process_id)
        and process_authorities.get(process.kind) == authority_id
        for process in state.processes
    ):
        operations.append("process_outcome")
    return tuple(operations)


def _continue_operation(
    model: PumpStationCoupledModel,
    state: PumpStationCoupledWorldState,
    *,
    request_id: str,
    reason: str,
) -> PumpStationCoupledTransition:
    event_time = _next_event_time(state)
    transition_id = f"transition-{state.sequence + 1}-{request_id}"
    advanced = _advance_physical(model, state, event_time, transition_id)
    interval = advanced.operating_intervals[-1]
    updated = _apply_event_effects(
        advanced,
        event_time=event_time,
        transition_id=transition_id,
    )
    return _finish_transition(
        state,
        updated,
        request_id=request_id,
        action_kind="continue_operation",
        actor_action=True,
        target_id=None,
        backlog_item_id=None,
        reason=reason,
        changed_record_ids=tuple(updated.event_effect_ids[len(state.event_effect_ids) :]),
        operating_interval_id=stewardship_content_id(interval, record_profile="v4"),
    )


def apply_coupled_actor_action(
    state: PumpStationCoupledWorldState,
    *,
    request_id: str,
    action_name: str,
    arguments: dict[str, Any],
    model: PumpStationCoupledModel | None = None,
) -> PumpStationCoupledTransition:
    """Apply one exact actor-interface-v2 action without accepting private overrides."""
    reason_value = arguments.get("reason")
    if not isinstance(reason_value, str) or not reason_value.strip():
        _fail("actor-action-arguments", "a non-empty natural-language reason is required")
    reason = reason_value.strip()
    if action_name == "continue_operation":
        return _continue_operation(
            model or _model(),
            state,
            request_id=request_id,
            reason=reason,
        )
    if action_name in {"search_evidence", "fetch_evidence"}:
        _fail("temporal-action-route", "search and fetch use the verified temporal gateway")

    target_value = arguments.get("pump_id")
    target_id = target_value if isinstance(target_value, str) else None
    backlog_value = arguments.get("backlog_item_id")
    backlog_item_id = backlog_value if isinstance(backlog_value, str) else None
    updated = state
    changed: tuple[str, ...] = ()
    if action_name == "request_duty_assignment":
        raw_assignment = arguments.get("ordered_pump_ids")
        if not isinstance(raw_assignment, list | tuple) or not raw_assignment:
            _fail("assignment", "ordered_pump_ids is required")
        assignment = tuple(str(value) for value in raw_assignment)
        pump_ids = {pump.pump_id for pump in state.physical.pumps}
        if len(assignment) > 2 or len(set(assignment)) != len(assignment) or not set(assignment) <= pump_ids:
            _fail("assignment", "assignment identities or count are invalid")
        if any(not state.physical.availability(pump_id).run_eligible for pump_id in assignment):
            _fail("assignment", "assignment contains a pump that cannot serve")
        source_outage_id = arguments.get("source_outage_id")
        if source_outage_id is not None and not any(
            episode.episode_id == source_outage_id and episode.status == "open" for episode in state.outage_episodes
        ):
            _fail("assignment-source", str(source_outage_id))
        source_backlog_item_id = arguments.get("source_backlog_item_id")
        if source_backlog_item_id is not None:
            source_item = state.backlog_item(str(source_backlog_item_id))
            if source_item.status in {
                PumpStationBacklogStatus.CLOSED,
                PumpStationBacklogStatus.CANCELLED,
                PumpStationBacklogStatus.SUPERSEDED,
            }:
                _fail("assignment-source", str(source_backlog_item_id))
        required = _service_requirement(state, state.calendar_seconds)
        selected = _selected_service_running(updated, assignment=assignment, required_scu=required)
        assured_available = sum(
            state.physical.availability(pump.pump_id).assured_for_outage_planning for pump in state.physical.pumps
        )
        if len(selected) < required and assured_available >= required:
            _fail("avoidable-service-deficit", "another permitted assignment can meet current service")
        assigned_service_scu = len(selected)
        unserved_service_scu = max(0, required - assigned_service_scu)
        assignment_record = PumpStationDutyAssignment(
            assignment_id=f"assignment-{state.sequence + 1}",
            ordered_pump_ids=assignment,
            active=True,
            source_need_id=f"service-{state.calendar_seconds}",
            effective_transition_id=f"request-{request_id}",
            required_service_scu=required,
            assigned_service_scu=assigned_service_scu,
            unserved_service_scu=unserved_service_scu,
            decision_detail=(
                "accepted unavoidable degraded operation" if unserved_service_scu else "accepted service assignment"
            ),
        )
        updated = replace(updated, assignment=assignment_record)
        updated = _with_physical_running_sets(updated, service=selected)
        changed = (assignment_record.assignment_id,)
    elif action_name in {
        "request_inspection",
        "request_obstruction_clearance",
        "request_functional_check",
        "request_post_maintenance_verification",
    }:
        if target_id is None or backlog_item_id is None:
            _fail("backlog-binding", "pump_id and current backlog_item_id are required")
        ranked = sort_eligible_backlog(
            state.backlog,
            now_calendar_seconds=state.calendar_seconds,
            runtime_clock_values=_runtime_clock_values(state),
        )
        selected_item = state.backlog_item(backlog_item_id)
        if ranked and ranked[0].item_id != selected_item.item_id and not reason:
            _fail("lower-ranked-reason", backlog_item_id)
        if action_name in {"request_inspection", "request_obstruction_clearance"}:
            if (
                target_id in state.assignment.ordered_pump_ids
                or target_id in state.physical.service_running_pump_ids
                or target_id in state.physical.test_running_pump_ids
            ):
                _fail("field-work-target", "target must be unassigned and not running")
        if action_name == "request_inspection":
            if selected_item.work_type not in {"inspection", "collateral_duty_inspection"}:
                _fail("backlog-binding", backlog_item_id)
            prior_mode = updated.physical.boundary(target_id).mode
            if prior_mode is not PumpStationPumpMode.SERVICE_AVAILABLE:
                _fail("inspection-boundary", target_id)
            updated = replace(
                updated,
                physical=updated.physical.with_boundary_mode(
                    target_id,
                    PumpStationPumpMode.ISOLATED_FOR_WORK,
                    request_id,
                ),
                restrictions=(
                    *updated.restrictions,
                    PumpStationRestriction(
                        restriction_id=f"isolation-{target_id}-{request_id}",
                        kind=PumpStationRestrictionKind.NO_INTERVENTION,
                        pump_id=target_id,
                        status=PumpStationRestrictionStatus.ACTIVE,
                        created_sequence=state.sequence + 1,
                    ),
                ),
            )
            updated = _start_process(
                updated,
                kind="inspection",
                target_id=target_id,
                backlog_item_id=backlog_item_id,
                duration_seconds=28_800,
                pool_ids=(
                    "field-access-slot",
                    "lifting-isolation-set-01",
                    "diagnostic-test-set-01",
                    "maintenance-crew-01",
                ),
            )
        elif action_name == "request_obstruction_clearance":
            if selected_item.work_type != "obstruction_clearance":
                _fail("backlog-binding", backlog_item_id)
            inspection_evidence_id = arguments.get("inspection_evidence_id")
            if inspection_evidence_id not in state.accepted_evidence_ids:
                _fail("clearance-evidence", str(inspection_evidence_id))
            expected_opening_evidence_id = f"initial-{target_id.removeprefix('pump-')}-inspection-accepted"
            if (
                selected_item.item_id == "backlog-b-clearance-001"
                and inspection_evidence_id != expected_opening_evidence_id
            ):
                _fail("clearance-evidence-binding", str(inspection_evidence_id))
            if state.physical.boundary(target_id).mode is not PumpStationPumpMode.ISOLATED_FOR_WORK:
                _fail("clearance-boundary", target_id)
            updated = _start_process(
                updated,
                kind="obstruction_clearance",
                target_id=target_id,
                backlog_item_id=backlog_item_id,
                duration_seconds=14_400,
                pool_ids=(
                    "field-access-slot",
                    "lifting-isolation-set-01",
                    "maintenance-crew-01",
                    "obstruction-clearance-kit",
                ),
            )
        elif action_name == "request_functional_check":
            if selected_item.work_type != "minimum_functional_check":
                _fail("backlog-binding", backlog_item_id)
            if state.physical.boundary(target_id).mode is not PumpStationPumpMode.TEST_ONLY:
                _fail("functional-check-boundary", target_id)
            updated = _start_process(
                updated,
                kind="functional_check",
                target_id=target_id,
                backlog_item_id=backlog_item_id,
                duration_seconds=3_600,
                pool_ids=(
                    "field-access-slot",
                    "diagnostic-test-set-01",
                    "maintenance-crew-01",
                ),
            )
            updated = _with_physical_running_sets(
                updated,
                service=updated.physical.service_running_pump_ids,
                test=(target_id,),
            )
        else:
            if selected_item.work_type != "post_maintenance_verification":
                _fail("backlog-binding", backlog_item_id)
            if state.physical.boundary(target_id).mode not in {
                PumpStationPumpMode.RUN_IN_SERVICE,
                PumpStationPumpMode.SERVICE_AVAILABLE,
            }:
                _fail("verification-boundary", target_id)
            updated = _start_process(
                updated,
                kind="post_maintenance_verification",
                target_id=target_id,
                backlog_item_id=backlog_item_id,
                duration_seconds=28_800,
                pool_ids=(
                    "field-access-slot",
                    "diagnostic-test-set-01",
                    "verification-engineer-01",
                ),
            )
        changed = (updated.processes[-1].process_id, backlog_item_id)
    elif action_name == "request_provisional_return":
        if target_id is None:
            _fail("provisional-return", "pump_id is required")
        evidence_id = arguments.get("functional_check_evidence_id")
        if evidence_id not in state.accepted_evidence_ids:
            _fail("provisional-return", "accepted functional-check evidence is required")
        expected_evidence_id = f"evidence-{target_id.removeprefix('pump-')}-functional-check-pass-001"
        if evidence_id != expected_evidence_id:
            _fail("provisional-return", "functional-check evidence belongs to another target")
        if state.physical.boundary(target_id).mode is not PumpStationPumpMode.TEST_ONLY:
            _fail("provisional-return", "pump is not in test_only")
        restriction_id = f"restriction-{target_id}-run-in-001"
        obligation_id = f"obligation-{target_id}-verification-001"
        updated = replace(
            updated,
            physical=updated.physical.with_boundary_mode(
                target_id,
                PumpStationPumpMode.RUN_IN_SERVICE,
                request_id,
            ),
            restrictions=(
                *updated.restrictions,
                PumpStationRestriction(
                    restriction_id=restriction_id,
                    kind=PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN,
                    pump_id=target_id,
                    status=PumpStationRestrictionStatus.ACTIVE,
                    created_sequence=state.sequence + 1,
                    evidence_id=str(evidence_id),
                ),
            ),
            obligations=(
                *updated.obligations,
                PumpStationObligation(
                    obligation_id=obligation_id,
                    kind=PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
                    pump_id=target_id,
                    status=PumpStationObligationStatus.ACTIVE,
                    originating_proposal_id=request_id,
                    responsible_authority=PumpStationAuthority.VERIFICATION,
                    linked_restriction_id=restriction_id,
                    due_calendar_seconds=state.calendar_seconds + 57_600,
                    due_runtime_seconds=(state.physical.pump(target_id).exposure.runtime_seconds + 28_800),
                    created_sequence=state.sequence + 1,
                    evidence_id=str(evidence_id),
                ),
            ),
        )
        runtime = updated.physical.pump(target_id).exposure.runtime_seconds
        generation, item = _generated_item(
            rule_id="WG-04",
            source_transition_id=f"transition-{state.sequence + 1}-{request_id}",
            target_kind="asset",
            target_id=target_id,
            ordinal=1,
            work_type="post_maintenance_verification",
            generated_at=state.calendar_seconds,
            priority=PumpStationPriority.P1,
            due_calendar_seconds=state.calendar_seconds + 57_600,
            due_runtime_kind="pump_total",
            due_runtime_id=target_id,
            due_runtime_limit=runtime + 28_800,
            obligation_ids=(obligation_id,),
            restriction_ids=(restriction_id,),
            closure_rule="verification accepted and Operations review releases run-in",
        )
        updated = _add_generated_work(updated, generation, item)
        changed = (restriction_id, obligation_id, item.item_id)
        backlog_item_id = item.item_id
    elif action_name == "request_provisional_closure":
        work_order_id = arguments.get("work_order_id")
        if not isinstance(work_order_id, str):
            _fail("provisional-closure", "work_order_id is required")
        changed = (f"provisional-closure-{work_order_id}",)
    elif action_name == "request_condition_check":
        if target_id is None:
            _fail("condition-check", "pump_id is required")
        evidence_id = f"condition-check-{target_id}-{state.sequence + 1}"
        updated = replace(
            updated,
            evidence=(
                *updated.evidence,
                _accepted_evidence_record(
                    evidence_id=evidence_id,
                    kind=PumpStationEvidenceKind.CONDITION_CHECK,
                    pump_id=target_id,
                    created_at_seconds=state.calendar_seconds,
                    produced_by=PumpStationAuthority.ENGINEERING,
                    accepted_by=PumpStationAuthority.ENGINEERING,
                ),
            ),
        )
        changed = (evidence_id,)
    elif action_name == "resume_process":
        if not state.physical.common_boundary.available:
            _fail("resume-process", "common operating boundary remains unavailable")
        process_value = arguments.get("process_id")
        matching = tuple(
            process
            for process in state.processes
            if process.process_id == process_value and process.status is PumpStationCoupledProcessStatus.SUSPENDED
        )
        if len(matching) != 1:
            _fail("resume-process", str(process_value))
        process = matching[0]
        _require_field_process_admissible(
            state,
            process_kind=process.kind,
            target_id=process.target_id,
            duration_seconds=process.remaining_duration_seconds,
        )
        resources, reservations = resume_process_reservations(
            state.resources,
            state.resource_reservations,
            process_id=process.process_id,
            target_id=process.target_id,
            required_pool_ids=process.required_pool_ids,
            now_calendar_seconds=state.calendar_seconds,
            remaining_duration_seconds=process.remaining_duration_seconds,
        )
        item = state.backlog_item(process.backlog_item_id)
        resumed_item = replace(
            item,
            status=PumpStationBacklogStatus.IN_PROGRESS,
            blocked_from_status=None,
            accumulated_blocked_seconds=(
                item.accumulated_blocked_seconds
                + state.calendar_seconds
                - (item.blocked_since_calendar_seconds or state.calendar_seconds)
            ),
            blocked_since_calendar_seconds=None,
        )
        resumed = replace(
            process,
            status=PumpStationCoupledProcessStatus.ACTIVE,
            due_at_calendar_seconds=state.calendar_seconds + process.remaining_duration_seconds,
        )
        updated = replace(
            _replace_backlog_item(state, resumed_item),
            resources=resources,
            resource_reservations=reservations,
            processes=tuple(resumed if value.process_id == process.process_id else value for value in state.processes),
        )
        if process.kind == "functional_check":
            updated = _with_physical_running_sets(
                updated,
                service=updated.physical.service_running_pump_ids,
                test=(process.target_id,),
            )
        target_id = process.target_id
        backlog_item_id = process.backlog_item_id
        changed = (process.process_id, process.backlog_item_id)
    elif action_name == "cancel_process":
        process_value = arguments.get("process_id")
        matching = tuple(
            process
            for process in state.processes
            if process.process_id == process_value and process.status is PumpStationCoupledProcessStatus.SUSPENDED
        )
        if len(matching) != 1:
            _fail("cancel-process", "active work must suspend before cancellation")
        process = matching[0]
        resources, reservations = cancel_process_reservations(
            state.resources,
            state.resource_reservations,
            process_id=process.process_id,
            now_calendar_seconds=state.calendar_seconds,
        )
        item = state.backlog_item(process.backlog_item_id)
        replanned = replace(
            item,
            status=PumpStationBacklogStatus.PLANNED,
            blocked_from_status=None,
            accumulated_blocked_seconds=(
                item.accumulated_blocked_seconds
                + state.calendar_seconds
                - (item.blocked_since_calendar_seconds or state.calendar_seconds)
            ),
            blocked_since_calendar_seconds=None,
            linked_process_id=None,
        )
        cancelled = replace(process, status=PumpStationCoupledProcessStatus.CANCELLED)
        updated = replace(
            _replace_backlog_item(state, replanned),
            resources=resources,
            resource_reservations=reservations,
            processes=tuple(
                cancelled if value.process_id == process.process_id else value for value in state.processes
            ),
        )
        target_id = process.target_id
        backlog_item_id = process.backlog_item_id
        changed = (process.process_id, process.backlog_item_id)
    elif action_name == "request_dependency_waiver":
        _fail("dependency-waiver", "RS1 has no waivable current dependency")
    else:
        _fail("unknown-actor-action", action_name)
    return _finish_transition(
        state,
        updated,
        request_id=request_id,
        action_kind=action_name,
        actor_action=True,
        target_id=target_id,
        backlog_item_id=backlog_item_id,
        reason=reason,
        changed_record_ids=changed,
    )


def apply_operations_boundary_review(
    state: PumpStationCoupledWorldState,
    request: PumpStationOperationsBoundaryReviewRequest,
) -> PumpStationCoupledTransition:
    """Apply one exact host-only Operations review after matching accepted evidence."""
    if request.version != PUMP_STATION_OPERATIONS_REVIEW_VERSION:
        _fail("operations-review-version", request.version)
    if "operations_review" not in pump_station_root_control_operations(
        state,
        authority_id=request.operations_authority_id,
    ):
        _fail("operations-review-authority", request.operations_authority_id)
    if request.base_state_id != state.state_id:
        _fail("stale-operations-review", request.review_id)
    if request.accepted_evidence_id not in state.accepted_evidence_ids:
        _fail("operations-review-evidence", request.accepted_evidence_id)
    expected_evidence_id = {
        "post_verification_restriction": (f"evidence-{request.pump_id}-verification-pass-001"),
        "post_inspection_isolation": (f"evidence-{request.pump_id.removeprefix('pump-')}-inspection-no-finding-001"),
    }.get(request.review_kind)
    if expected_evidence_id is not None and request.accepted_evidence_id != expected_evidence_id:
        _fail("operations-review-evidence-binding", request.accepted_evidence_id)
    if request.requested_outcome != "release":
        _fail("operations-review-outcome", request.requested_outcome)
    boundary = state.physical.boundary(request.pump_id)
    if request.review_kind == "post_verification_restriction":
        expected_mode = PumpStationPumpMode.RUN_IN_SERVICE
        expected_restriction = f"restriction-{request.pump_id}-run-in-001"
        obligation_id = f"obligation-{request.pump_id}-verification-001"
        if request.pump_id == "pump-a":
            expected_restriction = "restriction-a-run-in-001"
            obligation_id = "obligation-a-verification-001"
        if (
            boundary.mode is not expected_mode
            or request.restriction_or_isolation_permit_id != expected_restriction
            or expected_restriction not in state.active_restriction_ids
        ):
            _fail("operations-review-mismatch", request.review_id)
        updated = replace(
            state,
            physical=state.physical.with_boundary_mode(
                request.pump_id,
                PumpStationPumpMode.SERVICE_AVAILABLE,
                request.content_id,
            ),
            restrictions=tuple(
                replace(
                    value,
                    status=PumpStationRestrictionStatus.LIFTED,
                    evidence_id=request.accepted_evidence_id,
                )
                if value.restriction_id == expected_restriction
                else value
                for value in state.restrictions
            ),
            obligations=tuple(
                replace(
                    value,
                    status=PumpStationObligationStatus.FULFILLED,
                    evidence_id=request.accepted_evidence_id,
                )
                if value.obligation_id == obligation_id
                else value
                for value in state.obligations
            ),
        )
        matching = tuple(
            item
            for item in updated.backlog
            if item.target_id == request.pump_id
            and item.work_type == "post_maintenance_verification"
            and item.status is PumpStationBacklogStatus.COMPLETED
        )
        if len(matching) != 1:
            _fail("operations-review-work", request.pump_id)
        closed = replace(matching[0], status=PumpStationBacklogStatus.CLOSED)
        updated = _replace_backlog_item(updated, closed)
        if request.pump_id == "pump-b":
            updated = replace(
                updated,
                outage_episodes=tuple(
                    replace(
                        episode,
                        status="closed",
                        closing_transition_id=request.review_id,
                    )
                    if episode.episode_id == "outage-b-001"
                    else episode
                    for episode in updated.outage_episodes
                ),
            )
    elif request.review_kind == "post_inspection_isolation":
        isolation_id = f"isolation-{request.pump_id}-{request.restriction_or_isolation_permit_id.split('-')[-1]}"
        if boundary.mode is not PumpStationPumpMode.ISOLATED_FOR_WORK:
            _fail("operations-review-mismatch", request.review_id)
        matching_restrictions = tuple(
            value for value in state.active_restriction_ids if value.startswith(f"isolation-{request.pump_id}-")
        )
        if request.restriction_or_isolation_permit_id not in matching_restrictions:
            _fail("operations-review-mismatch", isolation_id)
        updated = replace(
            state,
            physical=state.physical.with_boundary_mode(
                request.pump_id,
                PumpStationPumpMode.SERVICE_AVAILABLE,
                request.content_id,
            ),
            restrictions=tuple(
                replace(
                    value,
                    status=PumpStationRestrictionStatus.LIFTED,
                    evidence_id=request.accepted_evidence_id,
                )
                if value.restriction_id in matching_restrictions
                else value
                for value in state.restrictions
            ),
        )
    else:
        _fail("operations-review-kind", request.review_kind)
    return _finish_transition(
        state,
        updated,
        request_id=request.review_id,
        action_kind="operations_boundary_review",
        actor_action=False,
        target_id=request.pump_id,
        backlog_item_id=None,
        reason=request.reason,
        changed_record_ids=(request.content_id, request.pump_id),
    )


def apply_coupled_treatment(
    state: PumpStationCoupledWorldState,
    request: PumpStationCoupledTreatmentRequest,
) -> PumpStationCoupledTransition:
    """Call the stable task-owned private treatment transition."""
    return _apply_stable_coupled_treatment(state, request)


def apply_process_outcome(
    state: PumpStationCoupledWorldState,
    request: PumpStationProcessOutcomeRequest,
) -> PumpStationCoupledTransition:
    """Record a failed functional or verification attempt without false closure."""
    if request.version != PUMP_STATION_PROCESS_OUTCOME_VERSION:
        _fail("process-outcome-version", request.version)
    if request.base_state_id != state.state_id:
        _fail("stale-process-outcome", request.request_id)
    if request.outcome != "failed":
        _fail("process-outcome", request.outcome)
    matching = tuple(
        process
        for process in state.processes
        if process.process_id == request.process_id and process.status is PumpStationCoupledProcessStatus.ACTIVE
    )
    if len(matching) != 1:
        _fail("process-outcome-process", request.process_id)
    process = matching[0]
    if "process_outcome" not in pump_station_root_control_operations(
        state,
        authority_id=request.authority_id,
        process_id=request.process_id,
    ):
        _fail("process-outcome-authority", request.authority_id)
    resources, reservations = release_reservations(
        state.resources,
        state.resource_reservations,
        process_id=process.process_id,
        now_calendar_seconds=state.calendar_seconds,
    )
    item = state.backlog_item(process.backlog_item_id)
    failed_item = replace(
        item,
        status=PumpStationBacklogStatus.PLANNED,
        linked_process_id=None,
        closure_evidence_ids=(*item.closure_evidence_ids, request.evidence_id),
    )
    failed_process = replace(
        process,
        status=PumpStationCoupledProcessStatus.FAILED,
    )
    physical = replace(
        state.physical,
        test_running_pump_ids=tuple(
            pump_id for pump_id in state.physical.test_running_pump_ids if pump_id != process.target_id
        ),
    )
    updated = replace(
        _replace_backlog_item(state, failed_item),
        physical=physical,
        resources=resources,
        resource_reservations=reservations,
        processes=tuple(
            failed_process if value.process_id == process.process_id else value for value in state.processes
        ),
        evidence=(
            *state.evidence,
            _accepted_evidence_record(
                evidence_id=request.evidence_id,
                kind=(
                    PumpStationEvidenceKind.FUNCTIONAL_CHECKS
                    if process.kind == "functional_check"
                    else PumpStationEvidenceKind.POST_MAINTENANCE_VERIFICATION
                ),
                pump_id=process.target_id,
                created_at_seconds=state.calendar_seconds,
                produced_by=(
                    PumpStationAuthority.MAINTENANCE
                    if process.kind == "functional_check"
                    else PumpStationAuthority.VERIFICATION
                ),
                accepted_by=(
                    PumpStationAuthority.MAINTENANCE
                    if process.kind == "functional_check"
                    else PumpStationAuthority.VERIFICATION
                ),
                passed=False,
            ),
        ),
    )
    changed = [process.process_id, item.item_id, request.evidence_id]
    if process.kind == "post_maintenance_verification":
        runtime = state.physical.pump(process.target_id).exposure.runtime_seconds
        generation, rework = _generated_item(
            rule_id="WG-05",
            source_transition_id=request.request_id,
            target_kind="asset",
            target_id=process.target_id,
            ordinal=1,
            work_type="rework_investigation",
            generated_at=state.calendar_seconds,
            priority=(
                PumpStationPriority.P0
                if process.target_id in state.physical.service_running_pump_ids
                else PumpStationPriority.P1
            ),
            due_calendar_seconds=state.calendar_seconds + 28_800,
            due_runtime_kind="pump_total",
            due_runtime_id=process.target_id,
            due_runtime_limit=runtime + 28_800,
            obligation_ids=failed_item.linked_obligation_ids,
            restriction_ids=failed_item.linked_restriction_ids,
            closure_rule="accepted rework investigation",
        )
        updated = _add_generated_work(updated, generation, rework)
        changed.append(rework.item_id)
    return _finish_transition(
        state,
        updated,
        request_id=request.request_id,
        action_kind="process_outcome",
        actor_action=False,
        target_id=process.target_id,
        backlog_item_id=process.backlog_item_id,
        reason="Record the authority-owned failed process evidence.",
        changed_record_ids=tuple(changed),
        authority_requirements=(("maintenance",) if process.kind == "functional_check" else ("verification",)),
    )


def apply_common_boundary_control(
    state: PumpStationCoupledWorldState,
    request: PumpStationCommonBoundaryRequest,
) -> PumpStationCoupledTransition:
    """Apply a station-wide hard stop or restoration before later decisions."""
    if request.version != PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION:
        _fail("common-boundary-version", request.version)
    if "common_boundary" not in pump_station_root_control_operations(
        state,
        authority_id=request.authority_id,
    ):
        _fail("common-boundary-authority", request.authority_id)
    if request.base_state_id != state.state_id:
        _fail("stale-common-boundary", request.request_id)
    if request.boundary_kind not in {"power", "discharge"}:
        _fail("common-boundary-kind", request.boundary_kind)
    updated = state
    if not request.available:
        for process in tuple(updated.processes):
            if process.status is PumpStationCoupledProcessStatus.ACTIVE:
                updated = _suspend_process(updated, process)
    boundary = replace(
        updated.physical.common_boundary,
        power_available=(
            request.available if request.boundary_kind == "power" else updated.physical.common_boundary.power_available
        ),
        discharge_available=(
            request.available
            if request.boundary_kind == "discharge"
            else updated.physical.common_boundary.discharge_available
        ),
        source_transition_id=request.content_id,
    )
    if not request.available:
        physical = replace(
            updated.physical,
            common_boundary=boundary,
            service_running_pump_ids=(),
            test_running_pump_ids=(),
        )
        assignment = replace(
            updated.assignment,
            active=False,
            suspension_source_id=request.content_id,
        )
    else:
        physical = replace(updated.physical, common_boundary=boundary)
        assignment = updated.assignment
    updated = replace(
        updated,
        physical=physical,
        assignment=assignment,
        event_effect_ids=(*updated.event_effect_ids, request.content_id),
    )
    return _finish_transition(
        state,
        updated,
        request_id=request.request_id,
        action_kind="common_boundary_control",
        actor_action=False,
        target_id=None,
        backlog_item_id=None,
        reason="Apply the declared common operating boundary change.",
        changed_record_ids=(request.content_id, request.boundary_kind),
    )


def apply_coupled_handover(
    state: PumpStationCoupledWorldState,
    *,
    handover_id: str,
    from_tenure_id: str,
    to_tenure_id: str,
) -> PumpStationCoupledTransition:
    """Publish one state-preserving tenure handover as a separate v4 control receipt."""
    if not from_tenure_id or not to_tenure_id or from_tenure_id == to_tenure_id:
        _fail("handover", "handover requires two distinct non-empty tenures")
    return _finish_transition(
        state,
        state,
        request_id=handover_id,
        action_kind="structured_handover",
        actor_action=False,
        target_id=None,
        backlog_item_id=None,
        reason="Carry the same verified live world to a fresh agent tenure.",
        changed_record_ids=(from_tenure_id, to_tenure_id),
    )


def _project_pump_availability(
    state: PumpStationCoupledWorldState,
    pump_id: str,
) -> PumpStationPumpAvailability:
    """Bind visible availability predicates to their canonical evidence and restriction sources."""
    return replace(
        state.physical.availability(pump_id),
        source_evidence_ids=tuple(
            evidence.evidence_id
            for evidence in state.evidence
            if evidence.pump_id == pump_id
            and evidence.accepted_by is not None
            and (evidence.health is None or evidence.health.accepted)
        ),
        source_restriction_ids=tuple(
            restriction.restriction_id
            for restriction in state.restrictions
            if restriction.pump_id == pump_id and restriction.status is PumpStationRestrictionStatus.ACTIVE
        ),
    )


def project_coupled_actor_view(
    state: PumpStationCoupledWorldState,
    *,
    episode_id: str = "oracle-episode",
    world_branch_id: str = "oracle-branch",
    actor_id: str = "reference-controller",
    agent_tenure_id: str = "reference-controller",
    source_artifact_ids: tuple[str, ...] = (),
) -> PumpStationCoupledActorView:
    """Project current v5 planning state without latent conditions or private events."""
    quantities: list[tuple[str, int, int]] = []
    for pool in state.resources.pools:
        if isinstance(pool, PumpStationReusablePool):
            quantities.append((pool.pool_id, pool.free, pool.reserved))
        elif isinstance(pool, PumpStationConsumablePool):
            quantities.append((pool.pool_id, pool.free, pool.reserved))
    reusable_pools = tuple(pool for pool in state.resources.pools if isinstance(pool, PumpStationReusablePool))
    resource_disclosed_through = max(
        (interval.end_calendar_seconds for pool in reusable_pools for interval in pool.availability_intervals),
        default=state.disclosed_through_calendar_seconds,
    )
    required_service_scu = _service_requirement(state, state.calendar_seconds)
    available_assured_scu = sum(
        state.physical.availability(pump.pump_id).assured_for_outage_planning for pump in state.physical.pumps
    )
    assigned_operating_scu = len(state.physical.service_running_pump_ids)
    served_scu = min(required_service_scu, assigned_operating_scu)
    view = PumpStationCoupledActorView(
        view_id="pending",
        episode_id=episode_id,
        world_branch_id=world_branch_id,
        actor_id=actor_id,
        agent_tenure_id=agent_tenure_id,
        source_artifact_ids=source_artifact_ids,
        projection_policy_id=PUMP_STATION_ACTOR_PROJECTION_VERSION_V5,
        observation_schema_id=PUMP_STATION_ACTOR_VIEW_SCHEMA_V4,
        information_boundary_id=PUMP_STATION_INFORMATION_BOUNDARY_V4,
        state_id=state.state_id,
        sequence=state.sequence,
        time_zone=PUMP_STATION_TIME_ZONE,
        current_datetime=pump_station_datetime(state.calendar_seconds),
        calendar_seconds=state.calendar_seconds,
        service_schedule=tuple(
            requirement
            for requirement in state.service_schedule
            if requirement.end_calendar_seconds > state.calendar_seconds
        ),
        disclosed_through_calendar_seconds=state.disclosed_through_calendar_seconds,
        service_schedule_disclosed_through_datetime=pump_station_datetime(state.disclosed_through_calendar_seconds),
        resource_schedule_disclosed_through_datetime=pump_station_datetime(resource_disclosed_through),
        service_schedule_local=tuple(
            (
                pump_station_datetime(requirement.start_calendar_seconds),
                pump_station_datetime(requirement.end_calendar_seconds),
                requirement.required_service_scu,
            )
            for requirement in state.service_schedule
            if requirement.end_calendar_seconds > state.calendar_seconds
        ),
        resource_availability_local=tuple(
            (
                pool.pool_id,
                tuple(
                    (
                        pump_station_datetime(interval.start_calendar_seconds),
                        pump_station_datetime(interval.end_calendar_seconds),
                    )
                    for interval in pool.availability_intervals
                    if interval.end_calendar_seconds > state.calendar_seconds
                ),
            )
            for pool in reusable_pools
        ),
        assignment_pump_ids=state.assignment.ordered_pump_ids,
        service_running_pump_ids=state.physical.service_running_pump_ids,
        test_running_pump_ids=state.physical.test_running_pump_ids,
        required_service_scu=required_service_scu,
        available_assured_scu=available_assured_scu,
        assigned_operating_scu=assigned_operating_scu,
        served_scu=served_scu,
        unserved_scu=max(0, required_service_scu - assigned_operating_scu),
        surplus_scu=max(0, assigned_operating_scu - required_service_scu),
        pump_clocks=tuple(
            (pump.pump_id, pump.exposure.runtime_seconds, pump.exposure.completed_starts)
            for pump in state.physical.pumps
        ),
        pump_runtime_display=tuple(
            (
                pump.pump_id,
                format_operating_duration(pump.exposure.runtime_seconds),
            )
            for pump in state.physical.pumps
        ),
        pump_boundaries=state.physical.pump_boundaries,
        pump_availability=tuple(_project_pump_availability(state, pump.pump_id) for pump in state.physical.pumps),
        resource_quantities=tuple(quantities),
        ranked_backlog=sort_eligible_backlog(
            state.backlog,
            now_calendar_seconds=state.calendar_seconds,
            runtime_clock_values=_runtime_clock_values(state),
        ),
        processes=state.processes,
        active_restriction_ids=state.active_restriction_ids,
        active_liability_ids=state.active_liability_ids,
        accepted_evidence_ids=state.accepted_evidence_ids,
        evidence_health=tuple(
            (
                item.evidence_id,
                item.pump_id,
                evidence_quality_at(
                    item.health.quality,
                    observed_at_seconds=item.health.observed_at_seconds,
                    now_seconds=state.calendar_seconds,
                ).value,
                item.health.accepted,
            )
            for item in state.evidence
            if item.health is not None
        ),
    )
    return view


def project_coupled_information_set(
    state: PumpStationCoupledWorldState,
    *,
    episode_id: str,
    world_branch_id: str,
    actor_id: str,
    agent_tenure_id: str,
    source_artifact_ids: tuple[str, ...],
    workspace_tool_ids: tuple[str, ...],
) -> PumpStationInformationSet:
    """Project the complete V4 actor view and its exact visible context."""
    view = project_coupled_actor_view(
        state,
        episode_id=episode_id,
        world_branch_id=world_branch_id,
        actor_id=actor_id,
        agent_tenure_id=agent_tenure_id,
        source_artifact_ids=source_artifact_ids,
    )
    return bind_information_set(
        view,
        PumpStationObservationHistory(
            agent_tenure_id=agent_tenure_id,
            view_ids=(view.view_id,),
        ),
        PumpStationCurrentContext(
            continuity_carrier=PumpStationContinuityCarrier.CURRENT_ACTOR_VIEW,
            conversation_prefix_id=None,
            workspace_tool_ids=workspace_tool_ids,
            visible_material_ids=source_artifact_ids,
        ),
    )
