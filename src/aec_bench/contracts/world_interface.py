# ABOUTME: Defines the opaque actor-decision boundary and the separate host-control protocol.
# ABOUTME: Keeps exact world bindings private while leaving task action payloads task-owned.

from __future__ import annotations

from typing import Any, Self

from pydantic import JsonValue, model_validator

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionOpenMode,
    WorldSessionRequest,
    WorldSessionResult,
)


class WorldInterfaceError(RuntimeError):
    """Raised when an actor or host-control call fails its closed contract."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class WorldActorActionCapability(FrozenStrictModel):
    """One task-owned action that an actor can discover and invoke."""

    name: NonEmptyStr
    description: NonEmptyStr
    input_schema: dict[str, JsonValue]


class WorldActorCapabilityCatalogue(FrozenStrictModel):
    """Current actor surface without host-only controls or durable identities."""

    task_world_id: NonEmptyStr
    actions: tuple[WorldActorActionCapability, ...]

    @model_validator(mode="after")
    def validate_catalogue(self) -> Self:
        names = tuple(action.name for action in self.actions)
        if not names:
            raise ValueError("actor capability catalogue must contain an action")
        if len(names) != len(set(names)):
            raise ValueError("actor action names must be distinct")
        return self


class WorldActorObservation(FrozenStrictModel):
    """One actor-visible view correlated by an opaque host-owned decision ID."""

    decision_id: NonEmptyStr
    view: dict[str, JsonValue]


class WorldActorActionRequest(FrozenStrictModel):
    """One task-owned action correlated to an opaque current decision."""

    request_id: NonEmptyStr
    decision_id: NonEmptyStr
    action_name: NonEmptyStr
    arguments: dict[str, JsonValue]


class WorldActorActionResult(FrozenStrictModel):
    """Current result of one task-owned actor action."""

    request_id: NonEmptyStr
    action_name: NonEmptyStr
    status: NonEmptyStr
    task_receipt: dict[str, JsonValue]
    next_observation: WorldActorObservation | None
    terminated: bool = False
    truncated: bool = False
    reason: str | None = None


class WorldControlOperationCapability(FrozenStrictModel):
    """One declared host-only operation and its durable-state effect."""

    operation: NonEmptyStr
    changes_durable_state: bool


class WorldControlCapabilityCatalogue(FrozenStrictModel):
    """Closed host-control surface for one task world."""

    task_world_id: NonEmptyStr
    operations: tuple[WorldControlOperationCapability, ...]

    @model_validator(mode="after")
    def validate_catalogue(self) -> Self:
        names = tuple(item.operation for item in self.operations)
        if not names:
            raise ValueError("world control catalogue must contain an operation")
        if len(names) != len(set(names)):
            raise ValueError("world control operation names must be distinct")
        return self


class WorldControlRequest(FrozenStrictModel):
    """One host-authorised request with no raw state mutation field."""

    request_id: NonEmptyStr
    operation: NonEmptyStr
    task_world_id: NonEmptyStr
    authority_id: NonEmptyStr
    session_request: WorldSessionRequest | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_raw_state(cls, value: Any) -> Any:
        if isinstance(value, dict) and "raw_state" in value:
            raise ValueError("world control request does not accept raw state")
        return value

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        session_operations = {"create_session", "open_session", "resume_session"}
        if self.operation in session_operations and self.session_request is None:
            raise ValueError(f"{self.operation} requires a session request")
        if self.operation not in session_operations and self.session_request is not None:
            raise ValueError(f"{self.operation} does not accept a session request")
        if (
            self.operation == "create_session"
            and self.session_request is not None
            and self.session_request.open_mode is not WorldSessionOpenMode.START
        ):
            raise ValueError("create_session requires start mode")
        if (
            self.operation == "resume_session"
            and self.session_request is not None
            and self.session_request.open_mode is not WorldSessionOpenMode.RESUME
        ):
            raise ValueError("resume_session requires resume mode")
        return self


class WorldControlReceipt(FrozenStrictModel):
    """Immutable receipt for one host-control request."""

    request_id: NonEmptyStr
    operation: NonEmptyStr
    authority_id: NonEmptyStr
    status: NonEmptyStr
    state_changed: bool
    prior_snapshot: StewardshipStateSnapshotRef | None = None
    result_snapshot: StewardshipStateSnapshotRef | None = None


class WorldControlProgress(FrozenStrictModel):
    """Task-neutral progress facts that do not expose raw world state."""

    snapshot: StewardshipStateSnapshotRef
    transition_count: int

    @model_validator(mode="after")
    def validate_progress(self) -> Self:
        if self.transition_count < 0:
            raise ValueError("world control transition count must be non-negative")
        if self.transition_count != self.snapshot.sequence:
            raise ValueError("world control transition count must match the snapshot sequence")
        return self


class WorldControlVerification(FrozenStrictModel):
    """Public result of independent task-owned replay verification."""

    valid: bool
    issues: tuple[str, ...]
    replayed_transition_ids: tuple[str, ...]
    final_state_id: NonEmptyStr


class WorldControlResult(FrozenStrictModel):
    """Typed machine-readable result from one host-only control operation."""

    request_id: NonEmptyStr
    receipt: WorldControlReceipt
    session_result: WorldSessionResult | None = None
    progress: WorldControlProgress | None = None
    snapshot: StewardshipStateSnapshotRef | None = None
    verification: WorldControlVerification | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        payloads = (
            self.session_result,
            self.progress,
            self.snapshot,
            self.verification,
        )
        if sum(item is not None for item in payloads) != 1:
            raise ValueError("world control result must contain exactly one typed payload")
        if self.receipt.request_id != self.request_id:
            raise ValueError("world control result and receipt request identities differ")
        return self
