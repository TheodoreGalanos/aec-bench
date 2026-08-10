# ABOUTME: Defines installed calls and optional persistent records for continual World capabilities.
# ABOUTME: Keeps these capabilities separate from the minimum Interactive World identity contract.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel, validate_sha256
from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class ContinualWorldActorRequest(FrozenStrictModel):
    """One current actor call using only an opaque host-owned decision reference."""

    operation: Literal["capabilities", "observe", "invoke"]
    request_id: NonEmptyStr | None = None
    decision_id: NonEmptyStr | None = None
    action_name: NonEmptyStr | None = None
    arguments: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_actor_request(self) -> Self:
        action_fields = (
            self.request_id,
            self.decision_id,
            self.action_name,
            self.arguments,
        )
        if self.operation != "invoke":
            if any(value is not None for value in action_fields):
                raise ValueError(f"continual actor {self.operation} accepts no action payload")
            return self
        if any(value is None for value in action_fields):
            raise ValueError("continual actor invoke requires request_id, decision_id, action_name, and arguments")
        return self


class ContinualControlCapabilitiesRequest(FrozenStrictModel):
    """Ask the selected run for its current host-control surface."""

    operation: Literal["capabilities"]
    authority_id: NonEmptyStr


class ContinualControlExecuteRequest(FrozenStrictModel):
    """Execute one task-owned control against the selected run."""

    operation: Literal["execute"]
    authority_id: NonEmptyStr
    control_request: dict[str, JsonValue]


class ContinualRolloutCreateRequest(FrozenStrictModel):
    """Persist one complete rollout-group request."""

    operation: Literal["create_rollout_group"]
    rollout_group_request: ContinualRolloutGroupRequest


class ContinualRolloutGroupQuery(FrozenStrictModel):
    """Inspect one rollout group through host-owned repository identity."""

    operation: Literal["rollout_group_status", "inspect_rollout_group"]
    authority_id: NonEmptyStr
    group_id: NonEmptyStr


class ContinualRolloutChildQuery(FrozenStrictModel):
    """Resolve one materialized rollout child through its host repository."""

    operation: Literal["rollout_child_run_ref"]
    authority_id: NonEmptyStr
    group_id: NonEmptyStr
    child_id: NonEmptyStr


type ContinualWorldControlRequest = Annotated[
    ContinualControlCapabilitiesRequest
    | ContinualControlExecuteRequest
    | ContinualRolloutCreateRequest
    | ContinualRolloutGroupQuery
    | ContinualRolloutChildQuery,
    Field(discriminator="operation"),
]


class ContinualWorldSnapshotRef(FrozenStrictModel):
    """Task-neutral identity of one immutable point on a selected world history."""

    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    sequence: int
    state_id: NonEmptyStr
    commit_id: NonEmptyStr

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if self.sequence < 0:
            raise ValueError("snapshot sequence must be non-negative")
        return self


class ContinualRolloutChildRequest(ContentAddressedModel):
    """One isolated child identity without actor, session, or treatment settings."""

    child_id: NonEmptyStr
    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_branch_id: NonEmptyStr


class ContinualRolloutGroupRequest(ContentAddressedModel):
    """One exact host request for ordered children from a verified snapshot."""

    request_id: NonEmptyStr
    group_id: NonEmptyStr
    task_world_id: NonEmptyStr
    authority_id: NonEmptyStr
    world_build: WorldBuildRef
    profile_ref: InteractiveWorldProfileRef
    parent_manifest_content_sha256: str
    parent_snapshot: ContinualWorldSnapshotRef
    origin_verification_content_sha256: str
    reason: NonEmptyStr
    children: tuple[ContinualRolloutChildRequest, ...]

    @field_validator("parent_manifest_content_sha256", "origin_verification_content_sha256")
    @classmethod
    def validate_group_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_group(self) -> Self:
        if self.world_build.task_world_id != self.task_world_id:
            raise ValueError("continual-world definition must belong to the requested task world")
        if self.profile_ref.task_world_id != self.task_world_id:
            raise ValueError("continual-world profile must belong to the requested task world")
        if not self.children:
            raise ValueError("continual rollout group requires at least one child")
        for field_name in ("child_id", "run_id", "episode_id", "world_branch_id"):
            values = tuple(getattr(child, field_name) for child in self.children)
            if len(values) != len(set(values)):
                label = field_name.replace("_", " ")
                raise ValueError(f"continual rollout child {label}s must be distinct")
        if any(
            child.run_id == self.parent_snapshot.run_id
            or child.episode_id == self.parent_snapshot.episode_id
            or child.world_branch_id == self.parent_snapshot.world_branch_id
            for child in self.children
        ):
            raise ValueError("continual rollout child world identity must differ from the parent")
        return self


class ContinualRolloutChildReceipt(ContentAddressedModel):
    """Immutable shared evidence for one verified child materialization."""

    group_id: NonEmptyStr
    child_id: NonEmptyStr
    child_request_content_sha256: str
    parent_snapshot: ContinualWorldSnapshotRef
    initial_snapshot: ContinualWorldSnapshotRef
    child_manifest_content_sha256: str
    task_branch_receipt_content_sha256: str
    ancestor_world_branch_ids: tuple[NonEmptyStr, ...]

    @field_validator(
        "child_request_content_sha256",
        "child_manifest_content_sha256",
        "task_branch_receipt_content_sha256",
    )
    @classmethod
    def validate_receipt_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if (
            self.initial_snapshot.sequence,
            self.initial_snapshot.state_id,
        ) != (
            self.parent_snapshot.sequence,
            self.parent_snapshot.state_id,
        ):
            raise ValueError("continual rollout child must open at the selected parent state")
        if not self.ancestor_world_branch_ids:
            raise ValueError("continual rollout receipt requires an ordered branch ancestry")
        if self.initial_snapshot.world_branch_id in self.ancestor_world_branch_ids:
            raise ValueError("continual rollout branch ancestry must exclude the child branch")
        if self.ancestor_world_branch_ids[-1] != self.parent_snapshot.world_branch_id:
            raise ValueError("continual rollout branch ancestry must end at the parent branch")
        if len(self.ancestor_world_branch_ids) != len(set(self.ancestor_world_branch_ids)):
            raise ValueError("continual rollout branch ancestry must not contain a cycle")
        return self


class ContinualRolloutLineage(ContentAddressedModel):
    """Complete immutable lineage for one ready rollout group."""

    request_id: NonEmptyStr
    group_id: NonEmptyStr
    task_world_id: NonEmptyStr
    world_build: WorldBuildRef
    profile_ref: InteractiveWorldProfileRef
    request_content_sha256: str
    parent_manifest_content_sha256: str
    parent_snapshot: ContinualWorldSnapshotRef
    origin_verification_content_sha256: str
    children: tuple[ContinualRolloutChildReceipt, ...]

    @field_validator(
        "request_content_sha256",
        "parent_manifest_content_sha256",
        "origin_verification_content_sha256",
    )
    @classmethod
    def validate_lineage_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_lineage(self) -> Self:
        if self.world_build.task_world_id != self.task_world_id:
            raise ValueError("continual rollout lineage definition belongs to another task world")
        if self.profile_ref.task_world_id != self.task_world_id:
            raise ValueError("continual rollout lineage profile belongs to another task world")
        if not self.children:
            raise ValueError("continual rollout lineage requires at least one child")
        if any(child.group_id != self.group_id for child in self.children):
            raise ValueError("continual rollout child receipt belongs to another group")
        if any(child.parent_snapshot != self.parent_snapshot for child in self.children):
            raise ValueError("continual rollout child receipt must use the lineage parent snapshot")
        child_ids = tuple(child.child_id for child in self.children)
        if len(child_ids) != len(set(child_ids)):
            raise ValueError("continual rollout lineage child ids must be distinct")
        return self


class ContinualRolloutGroupState(StrEnum):
    """Durable creation state for one rollout group."""

    PREPARING = "preparing"
    READY = "ready"


class ContinualRolloutGroupStatus(FrozenStrictModel):
    """Recoverable progress view for one rollout group."""

    group_id: NonEmptyStr
    request_id: NonEmptyStr
    state: ContinualRolloutGroupState
    requested_child_ids: tuple[NonEmptyStr, ...]
    created_child_ids: tuple[NonEmptyStr, ...]

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if not self.requested_child_ids:
            raise ValueError("continual rollout status requires requested children")
        if len(self.requested_child_ids) != len(set(self.requested_child_ids)):
            raise ValueError("continual rollout requested child ids must be distinct")
        if len(self.created_child_ids) != len(set(self.created_child_ids)):
            raise ValueError("continual rollout created child ids must be distinct")
        if any(child_id not in self.requested_child_ids for child_id in self.created_child_ids):
            raise ValueError("continual rollout created child is not in the request")
        requested_order = {child_id: index for index, child_id in enumerate(self.requested_child_ids)}
        if tuple(sorted(self.created_child_ids, key=requested_order.__getitem__)) != self.created_child_ids:
            raise ValueError("continual rollout created child ids must preserve request order")
        if self.state is ContinualRolloutGroupState.READY and self.created_child_ids != self.requested_child_ids:
            raise ValueError("ready continual rollout status requires every child")
        return self


class ContinualRolloutChildRunRef(FrozenStrictModel):
    """Private host reference for one materialized child run."""

    group_id: NonEmptyStr
    child_id: NonEmptyStr
    task_world_id: NonEmptyStr
    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    initial_snapshot: ContinualWorldSnapshotRef
    child_manifest_content_sha256: str

    @field_validator("child_manifest_content_sha256")
    @classmethod
    def validate_child_manifest_content_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_run_ref(self) -> Self:
        if (
            self.run_id,
            self.episode_id,
            self.world_branch_id,
        ) != (
            self.initial_snapshot.run_id,
            self.initial_snapshot.episode_id,
            self.initial_snapshot.world_branch_id,
        ):
            raise ValueError("continual rollout child identity differs from its initial snapshot")
        return self
