# ABOUTME: Defines immutable rollout-origin, child-lineage, and treatment receipts.
# ABOUTME: Keeps host-private branch facts separate from each actor-visible world view.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PumpStationPhysicalTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationRecordVersions,
    PumpStationStateSnapshotRef,
)

PUMP_STATION_ROLLOUT_REQUEST_VERSION = "pump-station.rollout-request.v1"
PUMP_STATION_ROLLOUT_LINEAGE_VERSION = "pump-station.rollout-lineage.v1"
PUMP_STATION_ROLLOUT_CHILD_RECEIPT_VERSION = "pump-station.rollout-child-receipt.v1"
PUMP_STATION_TREATMENT_RECEIPT_VERSION = "pump-station.treatment-receipt.v1"
PUMP_STATION_FIXED_CONDITION_POLICY = "fixed-future-conditions.v1"


class PumpStationRolloutGroupState(StrEnum):
    """Durable creation state for one declared rollout group."""

    PREPARING = "preparing"
    READY = "ready"


class PumpStationRolloutTreatmentStatus(StrEnum):
    """Private treatment progress state."""

    SCHEDULED = "scheduled"
    ACTIVATED = "activated"


@dataclass(frozen=True, slots=True)
class PumpStationRolloutChildRequest:
    """One requested isolated child and its agent-only variation."""

    child_id: str
    run_id: str
    world_branch_id: str
    agent_condition_id: str
    agent_seed: int


@dataclass(frozen=True, slots=True)
class PumpStationRolloutGroupRequest:
    """One idempotent host request for children from the current verified state."""

    request_id: str
    group_id: str
    task_world_id: str
    authority_id: str
    parent_snapshot: PumpStationStateSnapshotRef
    origin_verification_id: str
    information_boundary_id: str
    event_schedule_id: str
    fixed_future_condition_id: str
    future_condition_seed: int
    split_group_id: str
    children: tuple[PumpStationRolloutChildRequest, ...]
    request_version: str = PUMP_STATION_ROLLOUT_REQUEST_VERSION
    fixed_condition_policy: str = PUMP_STATION_FIXED_CONDITION_POLICY


@dataclass(frozen=True, slots=True)
class PumpStationRolloutChildReceipt:
    """Immutable creation evidence for one isolated child branch."""

    receipt_version: str
    group_id: str
    child_id: str
    parent_snapshot: PumpStationStateSnapshotRef
    initial_snapshot: PumpStationStateSnapshotRef
    record_versions: PumpStationRecordVersions
    package_content_id: str
    model_id: str
    information_boundary_id: str
    event_schedule_id: str
    event_schedule_sha256: str
    fixed_future_condition_id: str
    future_condition_seed: int
    agent_condition_id: str
    agent_seed: int
    split_group_id: str
    fixed_condition_policy: str


@dataclass(frozen=True, slots=True)
class PumpStationRolloutLineage:
    """Complete private lineage for one immutable rollout group."""

    lineage_version: str
    request_id: str
    group_id: str
    parent_snapshot: PumpStationStateSnapshotRef
    origin_verification_id: str
    origin_verification_sha256: str
    information_boundary_id: str
    event_schedule_id: str
    event_schedule_sha256: str
    fixed_future_condition_id: str
    future_condition_seed: int
    split_group_id: str
    fixed_condition_policy: str
    children: tuple[PumpStationRolloutChildReceipt, ...]


@dataclass(frozen=True, slots=True)
class PumpStationRolloutGroupStatus:
    """Recoverable progress view for one complete or interrupted group creation."""

    group_id: str
    request_id: str
    state: PumpStationRolloutGroupState
    requested_child_ids: tuple[str, ...]
    created_child_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PumpStationPhysicalTreatmentScheduleReceipt:
    """Private immutable declaration of one future child treatment."""

    receipt_version: str
    request: PumpStationPhysicalTreatmentRequest
    request_content_sha256: str
    status: PumpStationRolloutTreatmentStatus
    affected_pump_ids: tuple[str, ...]
    unaffected_pump_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PumpStationPhysicalTreatmentActivationReceipt:
    """Private immutable link from a treatment schedule to its realised child state."""

    receipt_version: str
    request: PumpStationPhysicalTreatmentRequest
    request_content_sha256: str
    activation_request_content_sha256: str
    status: PumpStationRolloutTreatmentStatus
    prior_snapshot: PumpStationStateSnapshotRef
    activation_snapshot: PumpStationStateSnapshotRef
    transition_id: str
    affected_pump_ids: tuple[str, ...]
    unaffected_pump_ids: tuple[str, ...]
