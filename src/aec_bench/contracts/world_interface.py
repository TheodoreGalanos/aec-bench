# ABOUTME: Defines task-neutral actor invocation and separate host-control envelopes.
# ABOUTME: Binds calls to exact public world identities without owning task action semantics.

from __future__ import annotations

from typing import Any, Self

from pydantic import JsonValue, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionOpenMode,
    WorldSessionRequest,
    WorldSessionResult,
)

WORLD_ACTOR_INTERFACE_SCHEMA_VERSION = "aecbench.world-actor-interface.v1"
WORLD_CONTROL_INTERFACE_SCHEMA_VERSION = "aecbench.world-control-interface.v1"


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


class WorldActorCapabilityCatalogue(ContentAddressedModel):
    """Closed actor surface without host-only controls or private world data."""

    schema_version: str = WORLD_ACTOR_INTERFACE_SCHEMA_VERSION
    task_world_id: NonEmptyStr
    interface_version: NonEmptyStr
    observation_schema_ref: NonEmptyStr
    actions: tuple[WorldActorActionCapability, ...]

    @model_validator(mode="after")
    def validate_catalogue(self) -> Self:
        if self.schema_version != WORLD_ACTOR_INTERFACE_SCHEMA_VERSION:
            raise ValueError("unsupported world actor interface schema version")
        names = tuple(action.name for action in self.actions)
        if not names:
            raise ValueError("actor capability catalogue must contain an action")
        if len(names) != len(set(names)):
            raise ValueError("actor action names must be distinct")
        return self


class WorldActorBinding(FrozenStrictModel):
    """Exact public session, state, view, and information binding for one call."""

    schema_version: str = WORLD_ACTOR_INTERFACE_SCHEMA_VERSION
    task_world_id: NonEmptyStr
    session_id: NonEmptyStr
    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    sequence: int
    state_id: NonEmptyStr
    commit_id: NonEmptyStr
    agent_tenure_id: NonEmptyStr
    actor_view_id: NonEmptyStr
    information_set_id: NonEmptyStr

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        if self.schema_version != WORLD_ACTOR_INTERFACE_SCHEMA_VERSION:
            raise ValueError("unsupported world actor interface schema version")
        if self.sequence < 0:
            raise ValueError("actor binding sequence must be non-negative")
        return self


class WorldActorObservation(ContentAddressedModel):
    """One content-addressed actor view and its exact invocation binding."""

    schema_version: str = WORLD_ACTOR_INTERFACE_SCHEMA_VERSION
    binding: WorldActorBinding
    view: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.schema_version != WORLD_ACTOR_INTERFACE_SCHEMA_VERSION:
            raise ValueError("unsupported world actor interface schema version")
        return self


class WorldActorActionRequest(ContentAddressedModel):
    """One idempotent actor request bound to an exact visible information set."""

    schema_version: str = WORLD_ACTOR_INTERFACE_SCHEMA_VERSION
    request_id: NonEmptyStr
    action_name: NonEmptyStr
    binding: WorldActorBinding
    arguments: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.schema_version != WORLD_ACTOR_INTERFACE_SCHEMA_VERSION:
            raise ValueError("unsupported world actor interface schema version")
        return self


class WorldActorActionResult(ContentAddressedModel):
    """Immutable public result of one task-owned actor action."""

    schema_version: str = WORLD_ACTOR_INTERFACE_SCHEMA_VERSION
    request_content_sha256: NonEmptyStr
    action_name: NonEmptyStr
    status: NonEmptyStr
    pre_binding: WorldActorBinding
    post_binding: WorldActorBinding
    task_receipt: dict[str, JsonValue]
    next_observation: WorldActorObservation

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.schema_version != WORLD_ACTOR_INTERFACE_SCHEMA_VERSION:
            raise ValueError("unsupported world actor interface schema version")
        if self.request_content_sha256 == self.content_sha256:
            raise ValueError("actor result identity must differ from its request identity")
        return self


class WorldControlOperationCapability(FrozenStrictModel):
    """One declared host-only operation and its durable-state effect."""

    operation: NonEmptyStr
    version: NonEmptyStr
    changes_durable_state: bool


class WorldControlCapabilityCatalogue(ContentAddressedModel):
    """Closed host-control surface for one task world."""

    schema_version: str = WORLD_CONTROL_INTERFACE_SCHEMA_VERSION
    task_world_id: NonEmptyStr
    interface_version: NonEmptyStr
    operations: tuple[WorldControlOperationCapability, ...]

    @model_validator(mode="after")
    def validate_catalogue(self) -> Self:
        if self.schema_version != WORLD_CONTROL_INTERFACE_SCHEMA_VERSION:
            raise ValueError("unsupported world control interface schema version")
        names = tuple(item.operation for item in self.operations)
        if not names:
            raise ValueError("world control catalogue must contain an operation")
        if len(names) != len(set(names)):
            raise ValueError("world control operation names must be distinct")
        return self


class WorldControlRequest(ContentAddressedModel):
    """One host-authorised request with no raw state mutation field."""

    schema_version: str = WORLD_CONTROL_INTERFACE_SCHEMA_VERSION
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
        if self.schema_version != WORLD_CONTROL_INTERFACE_SCHEMA_VERSION:
            raise ValueError("unsupported world control interface schema version")
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


class WorldControlReceipt(ContentAddressedModel):
    """Immutable receipt for one host-control request."""

    schema_version: str = WORLD_CONTROL_INTERFACE_SCHEMA_VERSION
    request_content_sha256: NonEmptyStr
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


class WorldControlResult(ContentAddressedModel):
    """Typed machine-readable result from one host-only control operation."""

    schema_version: str = WORLD_CONTROL_INTERFACE_SCHEMA_VERSION
    request_content_sha256: NonEmptyStr
    receipt: WorldControlReceipt
    session_result: WorldSessionResult | None = None
    progress: WorldControlProgress | None = None
    snapshot: StewardshipStateSnapshotRef | None = None
    verification: WorldControlVerification | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.schema_version != WORLD_CONTROL_INTERFACE_SCHEMA_VERSION:
            raise ValueError("unsupported world control interface schema version")
        payloads = (
            self.session_result,
            self.progress,
            self.snapshot,
            self.verification,
        )
        if sum(item is not None for item in payloads) != 1:
            raise ValueError("world control result must contain exactly one typed payload")
        if self.receipt.request_content_sha256 != self.request_content_sha256:
            raise ValueError("world control result and receipt request identities differ")
        return self
