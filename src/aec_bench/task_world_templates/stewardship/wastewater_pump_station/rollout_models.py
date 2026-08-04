# ABOUTME: Defines the private persisted receipt for one current registered rollout branch.
# ABOUTME: Contains no pump-specific rollout coordinator, treatment request, or live command family.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationStateSnapshotRef,
)


@dataclass(frozen=True, slots=True)
class PumpStationRolloutBranchReceipt:
    """Private persisted evidence for one materialized registered branch."""

    group_id: str
    child_id: str
    shared_group_request_content_sha256: str
    shared_child_request_content_sha256: str
    parent_snapshot: PumpStationStateSnapshotRef
    initial_snapshot: PumpStationStateSnapshotRef
    child_manifest_content_id: str
    temporal_bundle_content_id: str
    parent_origin_remaining_schedule_sha256: str
    ancestor_branch_ids: tuple[str, ...]


__all__: list[str] = []
