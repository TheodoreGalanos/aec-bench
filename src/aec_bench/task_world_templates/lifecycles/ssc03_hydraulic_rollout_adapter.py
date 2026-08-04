# ABOUTME: Adapts real SSC-03 submitted checkpoints to the shared continual rollout branch port.
# ABOUTME: Preserves lifecycle evidence and budgets while verifying exact retry and branch lineage.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildReceipt,
    ContinualRolloutChildRequest,
    ContinualRolloutGroupRequest,
    ContinualWorldSnapshotRef,
)
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleBranchSnapshot,
    EvidenceLifecycleError,
    branch_evidence_lifecycle,
    load_evidence_lifecycle_spec,
    read_evidence_lifecycle_branch_snapshot,
)
from aec_bench.meta_harness.evidence_lifecycle_state import (
    CheckpointRunStatus,
    EvidenceLifecycleRunState,
)
from aec_bench.task_world_templates.continual.branch_port import (
    ContinualWorldBranchMaterialization,
    ContinualWorldBranchPort,
    VerifiedContinualWorldBranchOrigin,
)
from aec_bench.task_world_templates.continual.durability import ImmutableByteStore

_ROOT_BRANCH_ID = "root"
_TASK_RECEIPT_PATH = "rollout-branch-receipt.json"


@dataclass(frozen=True, slots=True)
class Ssc03HydraulicRolloutOrigin:
    """Public exact request inputs for one submitted SSC-03 checkpoint."""

    parent_manifest_content_sha256: str
    parent_snapshot: ContinualWorldSnapshotRef
    origin_verification_content_sha256: str


class Ssc03HydraulicSubmittedCheckpointRef(ContentAddressedModel):
    """One immutable submitted checkpoint in an SSC-03 branch prefix."""

    checkpoint_id: NonEmptyStr
    submission_sha256: str

    @field_validator("submission_sha256")
    @classmethod
    def validate_submission_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class Ssc03HydraulicRolloutBranchReceipt(ContentAddressedModel):
    """Task-owned immutable evidence for one materialized SSC-03 child."""

    group_id: NonEmptyStr
    child_id: NonEmptyStr
    task_world_id: NonEmptyStr
    definition_content_sha256: str
    profile_content_sha256: str
    group_request_content_sha256: str
    child_request_content_sha256: str
    parent_manifest_content_sha256: str
    origin_verification_content_sha256: str
    parent_snapshot: ContinualWorldSnapshotRef
    initial_snapshot: ContinualWorldSnapshotRef
    lifecycle_id: NonEmptyStr
    lifecycle_spec_sha256: str
    package_sha256: str
    checkpoint_id: NonEmptyStr
    branch_id: NonEmptyStr
    parent_submission_sha256: str
    parent_action_state_sha256: str
    reason: NonEmptyStr
    submitted_checkpoint_prefix: tuple[Ssc03HydraulicSubmittedCheckpointRef, ...]
    ancestor_world_branch_ids: tuple[NonEmptyStr, ...]

    @field_validator(
        "definition_content_sha256",
        "profile_content_sha256",
        "group_request_content_sha256",
        "child_request_content_sha256",
        "parent_manifest_content_sha256",
        "origin_verification_content_sha256",
        "lifecycle_spec_sha256",
        "package_sha256",
        "parent_submission_sha256",
        "parent_action_state_sha256",
    )
    @classmethod
    def validate_receipt_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_branch_scope(self) -> Self:
        checkpoint_ids = tuple(item.checkpoint_id for item in self.submitted_checkpoint_prefix)
        if not checkpoint_ids or len(checkpoint_ids) != len(set(checkpoint_ids)):
            raise ValueError("SSC-03 rollout checkpoint prefix must be non-empty and ordered")
        if (
            checkpoint_ids[-1] != self.checkpoint_id
            or self.submitted_checkpoint_prefix[-1].submission_sha256 != self.parent_submission_sha256
        ):
            raise ValueError("SSC-03 rollout checkpoint prefix must end at the branch origin")
        if (
            self.initial_snapshot.sequence != self.parent_snapshot.sequence
            or self.initial_snapshot.state_id != self.parent_snapshot.state_id
            or self.initial_snapshot.world_branch_id != self.branch_id
        ):
            raise ValueError("SSC-03 rollout child snapshot differs from the branch scope")
        if (
            not self.ancestor_world_branch_ids
            or len(self.ancestor_world_branch_ids) != len(set(self.ancestor_world_branch_ids))
            or self.branch_id in self.ancestor_world_branch_ids
            or self.ancestor_world_branch_ids[-1] != self.parent_snapshot.world_branch_id
        ):
            raise ValueError("SSC-03 rollout branch ancestry is invalid")
        return self


@dataclass(frozen=True, slots=True)
class _Ssc03OriginContext:
    checkpoint_id: str
    checkpoint_index: int
    parent_action_state_sha256: str
    submitted_checkpoint_prefix: tuple[Ssc03HydraulicSubmittedCheckpointRef, ...]
    ancestor_world_branch_ids: tuple[str, ...]


class Ssc03HydraulicContinualBranchPort:
    """Real lifecycle implementation of the shared continual branch contract."""

    def verify_origin(
        self,
        *,
        profile_value: object,
        package_root: Path | None,
        parent_run_root: Path,
        request: ContinualRolloutGroupRequest,
    ) -> VerifiedContinualWorldBranchOrigin:
        package = _validated_package(profile_value, package_root)
        spec = load_evidence_lifecycle_spec(package)
        checkpoint_index = request.parent_snapshot.sequence - 1
        if checkpoint_index < 0 or checkpoint_index >= len(spec.checkpoints):
            raise ValueError("SSC-03 rollout snapshot sequence does not select a checkpoint")
        checkpoint_id = spec.checkpoints[checkpoint_index].checkpoint_id
        branch_snapshot = _validated_state(
            package,
            parent_run_root,
            checkpoint_id=checkpoint_id,
        )
        state = branch_snapshot.state
        expected = _origin_from_state(
            package,
            parent_run_root,
            state,
            checkpoint_id=checkpoint_id,
            branch_action_state_sha256=branch_snapshot.branch_action_state_sha256,
        )
        if expected.parent_snapshot != request.parent_snapshot:
            raise ValueError("SSC-03 rollout snapshot does not match the submitted checkpoint")
        if expected.parent_manifest_content_sha256 != request.parent_manifest_content_sha256:
            raise ValueError("SSC-03 rollout parent manifest does not match the lifecycle package")
        if expected.origin_verification_content_sha256 != request.origin_verification_content_sha256:
            raise ValueError("SSC-03 rollout origin verification content differs")
        _, ancestors = _run_identity_and_ancestor_branch_ids(package, parent_run_root, state)
        submitted_prefix = _submitted_checkpoint_prefix(state, checkpoint_index)
        return VerifiedContinualWorldBranchOrigin(
            parent_snapshot=expected.parent_snapshot,
            parent_manifest_content_sha256=expected.parent_manifest_content_sha256,
            origin_verification_content_sha256=expected.origin_verification_content_sha256,
            ancestor_world_branch_ids=ancestors,
            task_context=_Ssc03OriginContext(
                checkpoint_id=checkpoint_id,
                checkpoint_index=checkpoint_index,
                parent_action_state_sha256=expected.parent_snapshot.commit_id,
                submitted_checkpoint_prefix=submitted_prefix,
                ancestor_world_branch_ids=ancestors,
            ),
        )

    def materialize_child(
        self,
        *,
        profile_value: object,
        package_root: Path | None,
        parent_run_root: Path,
        child_run_root: Path,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        origin: VerifiedContinualWorldBranchOrigin,
    ) -> ContinualWorldBranchMaterialization:
        package = _validated_package(profile_value, package_root)
        context = origin.task_context
        if not isinstance(context, _Ssc03OriginContext):
            raise ValueError("SSC-03 rollout origin context is invalid")
        if child_run_root.is_symlink():
            raise ValueError("SSC-03 rollout child destination is unsafe")
        if not child_run_root.exists():
            try:
                branch_evidence_lifecycle(
                    package,
                    parent_run_root,
                    child_run_root,
                    checkpoint_id=context.checkpoint_id,
                    branch_id=child.world_branch_id,
                    reason=request.reason,
                    submission_validation_scope="selected-checkpoint-prefix",
                    expected_parent_submission_sha256=request.parent_snapshot.state_id,
                    expected_parent_action_state_sha256=context.parent_action_state_sha256,
                )
            except EvidenceLifecycleError:
                if not child_run_root.is_dir() or child_run_root.is_symlink():
                    raise
        initial_snapshot, task_receipt = _child_scope(
            package,
            parent_run_root,
            child_run_root,
            request,
            child,
            context,
        )
        artifact = _task_receipt_store(
            child_run_root,
            package_root=package,
            parent_run_root=parent_run_root,
        ).publish_bytes(
            _TASK_RECEIPT_PATH,
            _canonical_model_bytes(task_receipt),
        )
        return ContinualWorldBranchMaterialization(
            initial_snapshot=initial_snapshot,
            child_manifest_content_sha256=task_receipt.package_sha256,
            task_branch_receipt_content_sha256=artifact.sha256,
            ancestor_world_branch_ids=task_receipt.ancestor_world_branch_ids,
        )

    def verify_child(
        self,
        *,
        profile_value: object,
        package_root: Path | None,
        parent_run_root: Path,
        child_run_root: Path,
        request: ContinualRolloutGroupRequest,
        child: ContinualRolloutChildRequest,
        receipt: ContinualRolloutChildReceipt,
    ) -> None:
        package = _validated_package(profile_value, package_root)
        checkpoint_index = request.parent_snapshot.sequence - 1
        spec = load_evidence_lifecycle_spec(package)
        if checkpoint_index < 0 or checkpoint_index >= len(spec.checkpoints):
            raise ValueError("SSC-03 rollout receipt snapshot does not select a checkpoint")
        payload = _task_receipt_store(
            child_run_root,
            package_root=package,
            parent_run_root=parent_run_root,
        ).load_bytes(
            _TASK_RECEIPT_PATH,
            expected_sha256=receipt.task_branch_receipt_content_sha256,
        )
        task_receipt = Ssc03HydraulicRolloutBranchReceipt.model_validate_json(payload)
        context = _Ssc03OriginContext(
            checkpoint_id=spec.checkpoints[checkpoint_index].checkpoint_id,
            checkpoint_index=checkpoint_index,
            parent_action_state_sha256=request.parent_snapshot.commit_id,
            submitted_checkpoint_prefix=task_receipt.submitted_checkpoint_prefix,
            ancestor_world_branch_ids=receipt.ancestor_world_branch_ids,
        )
        initial_snapshot, expected_task_receipt = _child_scope(
            package,
            parent_run_root,
            child_run_root,
            request,
            child,
            context,
        )
        if task_receipt != expected_task_receipt:
            raise ValueError("SSC-03 rollout task receipt differs from the child")
        if (
            initial_snapshot != receipt.initial_snapshot
            or task_receipt.package_sha256 != receipt.child_manifest_content_sha256
            or task_receipt.ancestor_world_branch_ids != receipt.ancestor_world_branch_ids
        ):
            raise ValueError("SSC-03 rollout child differs from its immutable receipt")


def ssc03_hydraulic_rollout_origin(
    package_root: Path,
    parent_run_root: Path,
    *,
    checkpoint_id: str,
) -> Ssc03HydraulicRolloutOrigin:
    """Build exact generic origin fields for one submitted SSC-03 checkpoint."""
    package = Path(package_root)
    branch_snapshot = _validated_state(
        package,
        parent_run_root,
        checkpoint_id=checkpoint_id,
    )
    return _origin_from_state(
        package,
        parent_run_root,
        branch_snapshot.state,
        checkpoint_id=checkpoint_id,
        branch_action_state_sha256=branch_snapshot.branch_action_state_sha256,
    )


@cache
def ssc03_hydraulic_continual_branch_port() -> ContinualWorldBranchPort:
    """Return the registered SSC-03 branch port singleton."""
    return Ssc03HydraulicContinualBranchPort()


def _validated_package(profile_value: object, package_root: Path | None) -> Path:
    from aec_bench.task_world_templates.lifecycles.ssc03_hydraulic_continual_definition import (
        Ssc03HydraulicContinualProfile,
    )

    if package_root is None:
        raise ValueError("SSC-03 rollout requires the materialized lifecycle package")
    if not isinstance(profile_value, Ssc03HydraulicContinualProfile):
        raise ValueError("SSC-03 rollout requires its registered profile")
    package = Path(package_root)
    metadata = profile_value.validate_package(package)
    if metadata is None:
        raise ValueError("SSC-03 rollout lifecycle package is not valid")
    return package


def _validated_state(
    package_root: Path,
    run_root: Path,
    *,
    checkpoint_id: str,
) -> EvidenceLifecycleBranchSnapshot:
    return read_evidence_lifecycle_branch_snapshot(
        package_root,
        run_root,
        checkpoint_id=checkpoint_id,
    )


def _origin_from_state(
    package_root: Path,
    run_root: Path,
    state: EvidenceLifecycleRunState,
    *,
    checkpoint_id: str,
    branch_action_state_sha256: str,
) -> Ssc03HydraulicRolloutOrigin:
    spec = load_evidence_lifecycle_spec(package_root)
    try:
        checkpoint_index = next(
            index for index, checkpoint in enumerate(spec.checkpoints) if checkpoint.checkpoint_id == checkpoint_id
        )
    except StopIteration as exc:
        raise ValueError(f"unknown SSC-03 branch checkpoint: {checkpoint_id}") from exc
    checkpoint = state.checkpoint(checkpoint_id)
    if checkpoint.status is not CheckpointRunStatus.SUBMITTED or checkpoint.submission_sha256 is None:
        raise ValueError(f"SSC-03 checkpoint is not available for branching: {checkpoint_id}")
    branch_id = state.branch.branch_id if state.branch is not None else _ROOT_BRANCH_ID
    run_id, ancestors = _run_identity_and_ancestor_branch_ids(package_root, run_root, state)
    snapshot = ContinualWorldSnapshotRef(
        run_id=run_id,
        episode_id=_checkpoint_episode_id(checkpoint_id),
        world_branch_id=branch_id,
        sequence=checkpoint_index + 1,
        state_id=checkpoint.submission_sha256,
        commit_id=branch_action_state_sha256,
    )
    submitted_prefix = _submitted_checkpoint_prefix(state, checkpoint_index)
    verification_sha256 = canonical_content_sha256(
        {
            "lifecycle_id": state.lifecycle_id,
            "world_id": state.world_id,
            "lifecycle_spec_sha256": state.lifecycle_spec_sha256,
            "package_sha256": state.package_sha256,
            "checkpoint_id": checkpoint_id,
            "snapshot": snapshot.model_dump(mode="json"),
            "submitted_checkpoint_prefix": [item.model_dump(mode="json") for item in submitted_prefix],
            "ancestor_world_branch_ids": ancestors,
        }
    )
    return Ssc03HydraulicRolloutOrigin(
        parent_manifest_content_sha256=state.package_sha256,
        parent_snapshot=snapshot,
        origin_verification_content_sha256=verification_sha256,
    )


def _host_run_id(run_root: Path) -> str:
    selected = str(Path(run_root).expanduser().resolve(strict=True)).encode("utf-8")
    return f"ssc03-run-{hashlib.sha256(selected).hexdigest()}"


def _checkpoint_episode_id(checkpoint_id: str) -> str:
    return f"ssc03-checkpoint-{checkpoint_id}"


def _child_scope(
    package_root: Path,
    parent_run_root: Path,
    child_run_root: Path,
    request: ContinualRolloutGroupRequest,
    child: ContinualRolloutChildRequest,
    context: _Ssc03OriginContext,
) -> tuple[ContinualWorldSnapshotRef, Ssc03HydraulicRolloutBranchReceipt]:
    state = _validated_state(
        package_root,
        child_run_root,
        checkpoint_id=context.checkpoint_id,
    ).state
    branch = state.branch
    if branch is None:
        raise ValueError("SSC-03 rollout child is missing its branch record")
    if (
        branch.branch_id != child.world_branch_id
        or Path(branch.parent_run_dir).resolve() != Path(parent_run_root).resolve()
        or branch.branched_from_checkpoint_id != context.checkpoint_id
        or branch.parent_submission_sha256 != request.parent_snapshot.state_id
        or branch.parent_action_state_sha256 != context.parent_action_state_sha256
        or branch.reason != request.reason
        or state.active_checkpoint_id != context.checkpoint_id
    ):
        raise ValueError("SSC-03 rollout child branch record differs from the request")
    submitted_prefix = _child_submitted_checkpoint_prefix(
        state,
        branch_checkpoint_index=context.checkpoint_index,
        parent_submission_sha256=branch.parent_submission_sha256,
    )
    if submitted_prefix != context.submitted_checkpoint_prefix:
        raise ValueError("SSC-03 rollout child inherited submission prefix differs from the origin")
    initial_snapshot = ContinualWorldSnapshotRef(
        run_id=child.run_id,
        episode_id=child.episode_id,
        world_branch_id=child.world_branch_id,
        sequence=request.parent_snapshot.sequence,
        state_id=request.parent_snapshot.state_id,
        commit_id=canonical_content_sha256(
            {
                "child_request": child.model_dump(mode="json"),
                "parent_commit_id": request.parent_snapshot.commit_id,
                "branch": branch.model_dump(mode="json"),
            }
        ),
    )
    task_receipt = Ssc03HydraulicRolloutBranchReceipt(
        group_id=request.group_id,
        child_id=child.child_id,
        task_world_id=request.task_world_id,
        definition_content_sha256=request.world_build.artifact_sha256,
        profile_content_sha256=request.profile_ref.profile_content_sha256,
        group_request_content_sha256=request.content_sha256,
        child_request_content_sha256=child.content_sha256,
        parent_manifest_content_sha256=request.parent_manifest_content_sha256,
        origin_verification_content_sha256=request.origin_verification_content_sha256,
        parent_snapshot=request.parent_snapshot,
        initial_snapshot=initial_snapshot,
        lifecycle_id=state.lifecycle_id,
        lifecycle_spec_sha256=state.lifecycle_spec_sha256,
        package_sha256=state.package_sha256,
        checkpoint_id=context.checkpoint_id,
        branch_id=branch.branch_id,
        parent_submission_sha256=branch.parent_submission_sha256,
        parent_action_state_sha256=branch.parent_action_state_sha256,
        reason=branch.reason,
        submitted_checkpoint_prefix=submitted_prefix,
        ancestor_world_branch_ids=context.ancestor_world_branch_ids,
    )
    return initial_snapshot, task_receipt


def _task_receipt_store(
    child_run_root: Path,
    *,
    package_root: Path,
    parent_run_root: Path,
) -> ImmutableByteStore:
    return ImmutableByteStore(
        child_run_root,
        disjoint_roots=(package_root, parent_run_root),
        host_private=True,
    )


def _submitted_checkpoint_prefix(
    state: EvidenceLifecycleRunState,
    checkpoint_index: int,
) -> tuple[Ssc03HydraulicSubmittedCheckpointRef, ...]:
    prefix: list[Ssc03HydraulicSubmittedCheckpointRef] = []
    for checkpoint in state.checkpoint_runs[: checkpoint_index + 1]:
        if checkpoint.status is not CheckpointRunStatus.SUBMITTED or checkpoint.submission_sha256 is None:
            raise ValueError(f"SSC-03 checkpoint prefix is not submitted: {checkpoint.checkpoint_id}")
        prefix.append(
            Ssc03HydraulicSubmittedCheckpointRef(
                checkpoint_id=checkpoint.checkpoint_id,
                submission_sha256=checkpoint.submission_sha256,
            )
        )
    return tuple(prefix)


def _child_submitted_checkpoint_prefix(
    state: EvidenceLifecycleRunState,
    *,
    branch_checkpoint_index: int,
    parent_submission_sha256: str,
) -> tuple[Ssc03HydraulicSubmittedCheckpointRef, ...]:
    prefix = list(_submitted_checkpoint_prefix(state, branch_checkpoint_index - 1))
    checkpoint = state.checkpoint_runs[branch_checkpoint_index]
    if checkpoint.status is not CheckpointRunStatus.ACTIVE:
        raise ValueError("SSC-03 branch checkpoint is not active in the child")
    prefix.append(
        Ssc03HydraulicSubmittedCheckpointRef(
            checkpoint_id=checkpoint.checkpoint_id,
            submission_sha256=parent_submission_sha256,
        )
    )
    return tuple(prefix)


def _canonical_model_bytes(value: ContentAddressedModel) -> bytes:
    return json.dumps(
        value.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _run_identity_and_ancestor_branch_ids(
    package_root: Path,
    run_root: Path,
    state: EvidenceLifecycleRunState,
) -> tuple[str, tuple[str, ...]]:
    if state.branch is None:
        return _host_run_id(run_root), (_ROOT_BRANCH_ID,)
    store = ImmutableByteStore(
        run_root,
        disjoint_roots=(package_root,),
        host_private=True,
    )
    task_receipt = Ssc03HydraulicRolloutBranchReceipt.model_validate_json(store.load_bytes(_TASK_RECEIPT_PATH))
    branch = state.branch
    if (
        task_receipt.task_world_id != state.world_id
        or task_receipt.lifecycle_id != state.lifecycle_id
        or task_receipt.lifecycle_spec_sha256 != state.lifecycle_spec_sha256
        or task_receipt.package_sha256 != state.package_sha256
        or task_receipt.checkpoint_id != branch.branched_from_checkpoint_id
        or task_receipt.branch_id != branch.branch_id
        or task_receipt.parent_submission_sha256 != branch.parent_submission_sha256
        or task_receipt.parent_action_state_sha256 != branch.parent_action_state_sha256
        or task_receipt.reason != branch.reason
    ):
        raise ValueError("SSC-03 rollout ancestry receipt differs from the branch state")
    ancestors = task_receipt.ancestor_world_branch_ids
    if (
        not ancestors
        or len(ancestors) != len(set(ancestors))
        or branch.branch_id in ancestors
        or ancestors[-1] != task_receipt.parent_snapshot.world_branch_id
    ):
        raise ValueError("SSC-03 rollout ancestry receipt is invalid")
    return task_receipt.initial_snapshot.run_id, (*ancestors, branch.branch_id)


__all__ = [
    "Ssc03HydraulicContinualBranchPort",
    "Ssc03HydraulicRolloutBranchReceipt",
    "Ssc03HydraulicRolloutOrigin",
    "ssc03_hydraulic_continual_branch_port",
    "ssc03_hydraulic_rollout_origin",
]
