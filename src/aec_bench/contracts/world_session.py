# ABOUTME: Defines the minimal shared request, result, and dynamic snapshot contract for world sessions.
# ABOUTME: Keeps asset clocks, actions, views, and physical state outside the host-execution envelope.

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import model_validator

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

WORLD_SESSION_SCHEMA_VERSION = "aecbench.world-session.v1"


class WorldSessionExecutionKind(StrEnum):
    """Host execution kind for a persistent stewardship interaction."""

    STEWARDSHIP = "stewardship_world_session"


class WorldSessionOpenMode(StrEnum):
    """Supported ways to open one direct world session."""

    START = "start"
    RESUME = "resume"


class StewardshipStateSnapshotRef(FrozenStrictModel):
    """Task-neutral identity of one selected dynamic stewardship state."""

    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    sequence: int
    state_id: NonEmptyStr
    commit_id: NonEmptyStr

    @model_validator(mode="after")
    def validate_sequence(self) -> Self:
        if self.sequence < 0:
            raise ValueError("snapshot sequence must be non-negative")
        return self


class WorldSessionRequest(FrozenStrictModel):
    """Minimum host request shared by a session controller and one task world."""

    schema_version: str = WORLD_SESSION_SCHEMA_VERSION
    execution_kind: WorldSessionExecutionKind
    open_mode: WorldSessionOpenMode
    session_id: NonEmptyStr
    task_world_id: NonEmptyStr
    agent_tenure_id: NonEmptyStr
    run_id: NonEmptyStr
    episode_id: NonEmptyStr
    world_branch_id: NonEmptyStr
    start_snapshot: StewardshipStateSnapshotRef | None = None

    @model_validator(mode="after")
    def validate_open_mode(self) -> Self:
        if self.schema_version != WORLD_SESSION_SCHEMA_VERSION:
            raise ValueError("unsupported world-session schema version")
        if self.open_mode is WorldSessionOpenMode.START and self.start_snapshot is not None:
            raise ValueError("start request must not contain a prior snapshot")
        if self.open_mode is WorldSessionOpenMode.RESUME and self.start_snapshot is None:
            raise ValueError("resume request requires an exact start snapshot")
        if self.start_snapshot is not None and (
            self.start_snapshot.run_id,
            self.start_snapshot.episode_id,
            self.start_snapshot.world_branch_id,
        ) != (
            self.run_id,
            self.episode_id,
            self.world_branch_id,
        ):
            raise ValueError("start snapshot identity differs from the requested world")
        return self


class WorldSessionResult(FrozenStrictModel):
    """Current public host result for one opened world session."""

    schema_version: str = WORLD_SESSION_SCHEMA_VERSION
    execution_kind: WorldSessionExecutionKind
    open_mode: WorldSessionOpenMode
    session_id: NonEmptyStr
    task_world_id: NonEmptyStr
    agent_tenure_id: NonEmptyStr
    snapshot: StewardshipStateSnapshotRef
    actor_view_id: NonEmptyStr
    information_set_id: NonEmptyStr
    tool_names: tuple[NonEmptyStr, ...]

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.schema_version != WORLD_SESSION_SCHEMA_VERSION:
            raise ValueError("unsupported world-session schema version")
        if not self.tool_names:
            raise ValueError("world session must declare at least one tool")
        if len(set(self.tool_names)) != len(self.tool_names):
            raise ValueError("tool names must be distinct")
        return self
