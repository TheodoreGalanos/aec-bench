# ABOUTME: Exposes supported Interactive World branch creation through existing rollout authority.
# ABOUTME: Keeps child execution, evaluation, selection, merge, and parent mutation outside branching.

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildRequest,
    ContinualRolloutGroupRequest,
    ContinualRolloutLineage,
    ContinualWorldSnapshotRef,
)
from aec_bench.worlds.catalogue import _catalogue
from aec_bench.worlds.runtime.rollout_control import ContinualRolloutControl
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_rollout_adapter import (
    PumpStationContinualWorldBranchPort,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import PumpStationWorldRun
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)
from aec_bench.worlds.tasks import WorldTask, build_world_task


def branch_world(
    *,
    task: WorldTask,
    parent: PumpStationWorldRun,
    branches: Sequence[ContinualRolloutChildRequest],
    rollout_root: Path,
    authority_id: str,
    request_id: str,
    group_id: str,
    reason: str,
) -> ContinualRolloutLineage:
    """Create isolated pump children from one verified parent point only."""

    if "branching" not in _catalogue().resolve(task.world).capabilities:
        raise ValueError(f"Interactive World does not support branching: {task.world.task_world_id}")
    if task.world.task_world_id != PUMP_STATION_TASK_WORLD_ID:
        raise ValueError(f"unsupported Interactive World branch capability: {task.world.task_world_id}")
    if parent.world_build != task.world or parent.continual_profile_ref != task.profile:
        raise ValueError("branch parent does not match the WorldTask")
    selected = tuple(branches)
    if not selected:
        raise ValueError("world branching requires at least one child")
    snapshot = parent.snapshot()
    request = ContinualRolloutGroupRequest(
        request_id=request_id,
        group_id=group_id,
        task_world_id=task.world.task_world_id,
        authority_id=authority_id,
        world_build=task.world,
        profile_ref=task.profile,
        parent_manifest_content_sha256=pump_station_artifact_id(parent.manifest),
        parent_snapshot=ContinualWorldSnapshotRef(
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            sequence=snapshot.sequence,
            state_id=snapshot.state_id,
            commit_id=snapshot.commit_id,
        ),
        origin_verification_content_sha256=pump_station_artifact_id(parent.verify()),
        reason=reason,
        children=selected,
    )
    control = ContinualRolloutControl(
        _catalogue().resolve(task.world),
        PumpStationContinualWorldBranchPort(),
        parent_run_root=parent.repository.root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=(authority_id,),
    )
    return control.create_group(request)


def tasks_for_branches(task: WorldTask, lineage: ContinualRolloutLineage) -> tuple[WorldTask, ...]:
    """Create independent planned-task identities for materialized branch children."""

    if lineage.world_build != task.world or lineage.profile_ref != task.profile:
        raise ValueError("branch lineage does not match the WorldTask")
    return tuple(
        build_world_task(
            task_id=f"{task.task_id}/branches/{child.child_id}",
            instruction=task.instruction,
            world=task.world,
            profile=task.profile,
            domain=task.domain,
            category=task.category,
            difficulty=task.difficulty,
            lifecycle=task.lifecycle,
            visibility=task.visibility,
            tags=task.tags,
        )
        for child in lineage.children
    )


__all__ = ("branch_world", "tasks_for_branches")
