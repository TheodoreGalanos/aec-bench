# ABOUTME: Proves registered rollout children use the current episode host without a pump-specific runtime.
# ABOUTME: Covers exact origin binding, child isolation, opaque decisions, and replay verification.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildRequest,
    ContinualRolloutGroupRequest,
    ContinualWorldSnapshotRef,
)
from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.worlds.runtime.rollout_control import ContinualRolloutControl
from aec_bench.worlds.runtime.rollout_repository import ContinualRolloutRepository
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.continual_rollout_adapter import (
    PumpStationContinualWorldBranchPort,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
)


def _snapshot(run: PumpStationWorldRun) -> ContinualWorldSnapshotRef:
    selected = run.snapshot()
    return ContinualWorldSnapshotRef(
        run_id=selected.run_id,
        episode_id=selected.episode_id,
        world_branch_id=selected.world_branch_id,
        sequence=selected.sequence,
        state_id=selected.state_id,
        commit_id=selected.commit_id,
    )


def test_registered_rollout_children_share_origin_then_advance_independently(
    tmp_path: Path,
) -> None:
    definition = pump_station_continual_world_definition()
    profile_ref = definition.profiles[0]
    parent_root = tmp_path / "parent"
    parent = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(parent_root),
        run_id="rollout-parent-run",
        episode_id="rollout-parent-episode",
        world_branch_id="rollout-parent-branch",
    )
    parent_before = parent.snapshot()
    rollout_root = tmp_path / "rollouts"
    request = ContinualRolloutGroupRequest(
        request_id="registered-rollout-request",
        group_id="registered-rollout-group",
        task_world_id=definition.ref.task_world_id,
        authority_id="rollout-host",
        world_build=definition.build,
        profile_ref=profile_ref,
        parent_manifest_content_sha256=pump_station_artifact_id(parent.manifest),
        parent_snapshot=_snapshot(parent),
        origin_verification_content_sha256=pump_station_artifact_id(parent.verify()),
        reason="Create two isolated branches from the verified registered origin.",
        children=tuple(
            ContinualRolloutChildRequest(
                child_id=child_id,
                run_id=f"rollout-{child_id}-run",
                episode_id=f"rollout-{child_id}-episode",
                world_branch_id=f"rollout-{child_id}-branch",
            )
            for child_id in ("control", "candidate")
        ),
    )
    control = ContinualRolloutControl(
        definition,
        PumpStationContinualWorldBranchPort(),
        parent_run_root=parent_root,
        rollout_repository_root=rollout_root,
        authorised_principal_ids=("rollout-host",),
    )

    lineage = control.create_group(request)
    repository = ContinualRolloutRepository(
        rollout_root,
        disjoint_roots=(parent_root,),
    )
    control_root = repository.child_world_root(request.group_id, "control")
    candidate_root = repository.child_world_root(request.group_id, "candidate")
    control_run = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(control_root),
        snapshot=PumpStationWorldRunRepository(control_root).current_snapshot(),
    )
    candidate_run = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(candidate_root),
        snapshot=PumpStationWorldRunRepository(candidate_root).current_snapshot(),
    )
    control_before = control_run.snapshot()
    candidate_host = PumpStationEpisodeHost(candidate_root)
    decision = candidate_host.observe()
    candidate_host.invoke(
        WorldActorActionRequest(
            request_id="candidate-condition-check",
            decision_id=decision.decision_id,
            action_name="request_condition_check",
            arguments={
                "pump_id": "pump-b",
                "reason": "Advance only the selected candidate child.",
            },
        )
    )

    assert tuple(receipt.child_id for receipt in lineage.children) == ("control", "candidate")
    assert parent.snapshot() == parent_before
    assert control_run.snapshot() == control_before
    assert candidate_run.snapshot().sequence == parent_before.sequence + 1
    assert candidate_run.verify().valid
    assert control_run.verify().valid
