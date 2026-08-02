# ABOUTME: Tests the task-neutral records for chosen-point continual-world rollout groups.
# ABOUTME: Proves exact identity, ordered children, and exclusion of actor execution settings.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildReceipt,
    ContinualRolloutChildRequest,
    ContinualRolloutGroupRequest,
    ContinualRolloutGroupState,
    ContinualRolloutGroupStatus,
    ContinualRolloutLineage,
    ContinualWorldDefinitionRef,
    ContinualWorldProfileRef,
    ContinualWorldSnapshotRef,
)


def _snapshot() -> ContinualWorldSnapshotRef:
    return ContinualWorldSnapshotRef(
        run_id="parent-run",
        episode_id="parent-episode",
        world_branch_id="root",
        sequence=7,
        state_id="state-7",
        commit_id="commit-7",
    )


def _request(**updates: object) -> ContinualRolloutGroupRequest:
    values: dict[str, object] = {
        "request_id": "request-1",
        "group_id": "group-1",
        "task_world_id": "world.example",
        "authority_id": "host-control",
        "definition_ref": ContinualWorldDefinitionRef(
            task_world_id="world.example",
            definition_version="1",
            content_sha256="a" * 64,
        ),
        "profile_ref": ContinualWorldProfileRef(
            task_world_id="world.example",
            profile_id="profile.example",
            profile_version="1",
            profile_content_sha256="b" * 64,
        ),
        "parent_manifest_content_sha256": "c" * 64,
        "parent_snapshot": _snapshot(),
        "origin_verification_content_sha256": "d" * 64,
        "reason": "Compare two deterministic continuations.",
        "children": (
            ContinualRolloutChildRequest(
                child_id="child-a",
                run_id="child-run-a",
                episode_id="child-episode-a",
                world_branch_id="branch-a",
            ),
            ContinualRolloutChildRequest(
                child_id="child-b",
                run_id="child-run-b",
                episode_id="child-episode-b",
                world_branch_id="branch-b",
            ),
        ),
    }
    values.update(updates)
    return ContinualRolloutGroupRequest(**values)


def test_rollout_group_request_has_stable_content_identity_and_child_order() -> None:
    request = _request()
    recovered = ContinualRolloutGroupRequest.model_validate(request.model_dump(mode="json"))

    assert recovered == request
    assert recovered.content_sha256 == request.content_sha256
    assert tuple(child.child_id for child in recovered.children) == ("child-a", "child-b")
    assert all(child.content_sha256 for child in recovered.children)


@pytest.mark.parametrize("identity_field", ("child_id", "run_id", "episode_id", "world_branch_id"))
def test_rollout_group_request_rejects_reused_child_identity(identity_field: str) -> None:
    first, second = _request().children
    duplicate_payload = second.model_dump(mode="python", exclude={"content_sha256"})
    duplicate_payload[identity_field] = getattr(first, identity_field)
    duplicate = ContinualRolloutChildRequest(**duplicate_payload)

    with pytest.raises(ValidationError, match=f"{identity_field.replace('_', ' ')}s must be distinct"):
        _request(children=(first, duplicate))


def test_rollout_group_request_rejects_foreign_definition_or_profile() -> None:
    request = _request()
    foreign_definition = request.definition_ref.model_copy(update={"task_world_id": "world.foreign"})
    foreign_profile = request.profile_ref.model_copy(update={"task_world_id": "world.foreign"})

    with pytest.raises(ValidationError, match="definition must belong to the requested task world"):
        _request(definition_ref=foreign_definition)
    with pytest.raises(ValidationError, match="profile must belong to the requested task world"):
        _request(profile_ref=foreign_profile)


@pytest.mark.parametrize(
    ("identity_field", "parent_value"),
    (
        ("run_id", "parent-run"),
        ("episode_id", "parent-episode"),
        ("world_branch_id", "root"),
    ),
)
def test_rollout_group_request_rejects_child_identity_reused_from_parent(
    identity_field: str,
    parent_value: str,
) -> None:
    child_payload = _request().children[0].model_dump(mode="python", exclude={"content_sha256"})
    child_payload[identity_field] = parent_value

    with pytest.raises(ValidationError, match="child world identity must differ from the parent"):
        _request(children=(ContinualRolloutChildRequest(**child_payload),))


def test_rollout_child_receipt_ancestry_ends_at_parent_and_excludes_child() -> None:
    request = _request()
    child = request.children[0]
    initial = ContinualWorldSnapshotRef(
        run_id=child.run_id,
        episode_id=child.episode_id,
        world_branch_id=child.world_branch_id,
        sequence=request.parent_snapshot.sequence,
        state_id=request.parent_snapshot.state_id,
        commit_id="child-commit-7",
    )

    receipt = ContinualRolloutChildReceipt(
        group_id=request.group_id,
        child_id=child.child_id,
        child_request_content_sha256=child.content_sha256,
        parent_snapshot=request.parent_snapshot,
        initial_snapshot=initial,
        child_manifest_content_sha256="e" * 64,
        task_branch_receipt_content_sha256="f" * 64,
        ancestor_world_branch_ids=(request.parent_snapshot.world_branch_id,),
    )

    assert receipt.ancestor_world_branch_ids == ("root",)
    with pytest.raises(ValidationError, match="must exclude the child branch"):
        ContinualRolloutChildReceipt.model_validate(
            {
                **receipt.model_dump(mode="python", exclude={"content_sha256"}),
                "ancestor_world_branch_ids": ("root", child.world_branch_id),
            }
        )
    with pytest.raises(ValidationError, match="must end at the parent branch"):
        ContinualRolloutChildReceipt.model_validate(
            {
                **receipt.model_dump(mode="python", exclude={"content_sha256"}),
                "ancestor_world_branch_ids": ("foreign",),
            }
        )


def test_rollout_lineage_rejects_child_receipt_from_another_parent_snapshot() -> None:
    request = _request()
    child = request.children[0]
    foreign_parent = ContinualWorldSnapshotRef(
        run_id="foreign-parent-run",
        episode_id="foreign-parent-episode",
        world_branch_id="foreign-parent-branch",
        sequence=request.parent_snapshot.sequence,
        state_id=request.parent_snapshot.state_id,
        commit_id=request.parent_snapshot.commit_id,
    )
    receipt = ContinualRolloutChildReceipt(
        group_id=request.group_id,
        child_id=child.child_id,
        child_request_content_sha256=child.content_sha256,
        parent_snapshot=foreign_parent,
        initial_snapshot=ContinualWorldSnapshotRef(
            run_id=child.run_id,
            episode_id=child.episode_id,
            world_branch_id=child.world_branch_id,
            sequence=foreign_parent.sequence,
            state_id=foreign_parent.state_id,
            commit_id="child-commit-7",
        ),
        child_manifest_content_sha256="e" * 64,
        task_branch_receipt_content_sha256="f" * 64,
        ancestor_world_branch_ids=(foreign_parent.world_branch_id,),
    )

    with pytest.raises(ValidationError, match="child receipt must use the lineage parent snapshot"):
        ContinualRolloutLineage(
            request_id=request.request_id,
            group_id=request.group_id,
            task_world_id=request.task_world_id,
            definition_ref=request.definition_ref,
            profile_ref=request.profile_ref,
            request_content_sha256=request.content_sha256,
            parent_manifest_content_sha256=request.parent_manifest_content_sha256,
            parent_snapshot=request.parent_snapshot,
            origin_verification_content_sha256=request.origin_verification_content_sha256,
            children=(receipt,),
        )


def test_rollout_group_status_rejects_duplicate_created_child_ids() -> None:
    with pytest.raises(ValidationError, match="created child ids must be distinct"):
        ContinualRolloutGroupStatus(
            group_id="group-1",
            request_id="request-1",
            state=ContinualRolloutGroupState.PREPARING,
            requested_child_ids=("child-a", "child-b"),
            created_child_ids=("child-a", "child-a"),
        )


def test_generic_rollout_child_rejects_actor_and_provider_settings() -> None:
    with pytest.raises(ValidationError):
        ContinualRolloutChildRequest.model_validate(
            {
                "child_id": "child-a",
                "run_id": "child-run-a",
                "episode_id": "child-episode-a",
                "world_branch_id": "branch-a",
                "agent_condition_id": "agent-condition-a",
                "agent_seed": 41,
                "provider": "provider-a",
                "model": "model-a",
            }
        )


def test_continual_snapshot_rejects_negative_sequence() -> None:
    with pytest.raises(ValidationError, match="snapshot sequence must be non-negative"):
        ContinualWorldSnapshotRef(
            run_id="parent-run",
            episode_id="parent-episode",
            world_branch_id="root",
            sequence=-1,
            state_id="state-7",
            commit_id="commit-7",
        )
