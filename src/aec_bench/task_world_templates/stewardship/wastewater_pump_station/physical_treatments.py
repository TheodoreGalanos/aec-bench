# ABOUTME: Defines closed, host-owned physical treatment inputs for rollout children.
# ABOUTME: Applies bounded deterministic effects without exposing treatment labels to actors.

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpCondition,
    PumpState,
    PumpStationChangeKind,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationStewardshipState,
)

PUMP_STATION_PHYSICAL_TREATMENT_VERSION = "pump-station.physical-treatment.v1"
PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY = "normal-world-observations-only.v1"
PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT = "task-owned-physical-treatment-control"


class PumpStationPhysicalTreatmentClass(StrEnum):
    """Closed future-world mechanisms supported by the pump-station task."""

    CONTINUED_OBSTRUCTION = "continued_obstruction"
    RECURRENT_OBSTRUCTION = "recurrent_obstruction"
    RESTORATION_SHORTFALL = "restoration_shortfall"
    MAINTENANCE_INDUCED_CLEARANCE_LOSS = "maintenance_induced_clearance_loss"
    COMMON_CAUSE_OBSTRUCTION = "common_cause_obstruction"
    CLEARANCE_REPAIR_ALTERNATIVE = "clearance_repair_alternative"


class PumpStationTreatmentSeverity(StrEnum):
    """Bounded task-owned effect band rather than a direct latent assignment."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class PumpStationPhysicalTreatmentRequest:
    """One private treatment declaration bound to an eligible child snapshot."""

    request_id: str
    task_world_id: str
    authority_id: str
    group_id: str
    child_id: str
    child_run_id: str
    child_episode_id: str
    child_world_branch_id: str
    base_state_id: str
    base_commit_id: str
    based_on_sequence: int
    parent_state_id: str
    treatment_class: PumpStationPhysicalTreatmentClass
    treatment_version: str
    affected_pump_ids: tuple[str, ...]
    activation_calendar_seconds: int
    severity: PumpStationTreatmentSeverity
    random_stream_id: str
    random_seed: int
    visibility_policy: str
    decision_right_id: str


@dataclass(frozen=True, slots=True)
class PumpStationPhysicalTreatmentActivationRequest:
    """Durable realised treatment input bound to the current child state."""

    request_id: str
    schedule_request_id: str
    run_id: str
    episode_id: str
    world_branch_id: str
    base_state_id: str
    base_commit_id: str
    based_on_sequence: int
    parent_state_id: str
    treatment_class: PumpStationPhysicalTreatmentClass
    treatment_version: str
    affected_pump_ids: tuple[str, ...]
    activation_calendar_seconds: int
    severity: PumpStationTreatmentSeverity
    random_stream_id: str
    random_seed: int
    visibility_policy: str
    decision_right_id: str


def apply_physical_treatment_effect(
    state: PumpStationStewardshipState,
    request: PumpStationPhysicalTreatmentActivationRequest,
) -> tuple[PumpStationStewardshipState, PumpStationChangeKind]:
    """Apply one bounded task-owned mechanism to the selected child state."""

    magnitude = _effect_magnitude(request)
    physical = state.physical
    for pump_id in request.affected_pump_ids:
        pump = physical.pump(pump_id)
        condition = _treated_condition(pump, request.treatment_class, magnitude)
        physical = physical.with_pump(replace(pump, condition=condition))
    return replace(state, physical=physical), PumpStationChangeKind.GOVERNED_TREATMENT


def _effect_magnitude(request: PumpStationPhysicalTreatmentActivationRequest) -> Decimal:
    base = {
        PumpStationTreatmentSeverity.LOW: Decimal("0.08"),
        PumpStationTreatmentSeverity.MODERATE: Decimal("0.16"),
        PumpStationTreatmentSeverity.HIGH: Decimal("0.28"),
    }[request.severity]
    material = (
        f"{request.random_stream_id}:{request.random_seed}:"
        f"{request.treatment_class.value}:{','.join(request.affected_pump_ids)}"
    ).encode()
    draw = int.from_bytes(hashlib.sha256(material).digest()[:2], "big") % 41
    return base + Decimal(draw) / Decimal(1000)


def _treated_condition(
    pump: PumpState,
    treatment_class: PumpStationPhysicalTreatmentClass,
    magnitude: Decimal,
) -> PumpCondition:
    condition = pump.condition
    if treatment_class in {
        PumpStationPhysicalTreatmentClass.CONTINUED_OBSTRUCTION,
        PumpStationPhysicalTreatmentClass.RESTORATION_SHORTFALL,
    }:
        return replace(condition, obstruction=max(condition.obstruction, magnitude))
    if treatment_class in {
        PumpStationPhysicalTreatmentClass.RECURRENT_OBSTRUCTION,
        PumpStationPhysicalTreatmentClass.COMMON_CAUSE_OBSTRUCTION,
    }:
        return replace(
            condition,
            obstruction=min(Decimal(1), condition.obstruction + magnitude),
        )
    if treatment_class is PumpStationPhysicalTreatmentClass.MAINTENANCE_INDUCED_CLEARANCE_LOSS:
        return replace(
            condition,
            clearance_loss=min(Decimal(1), condition.clearance_loss + magnitude),
        )
    return replace(
        condition,
        clearance_loss=max(Decimal(0), condition.clearance_loss * (Decimal(1) - magnitude)),
    )
