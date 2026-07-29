# ABOUTME: Validates the provider-neutral host boundary used to open direct world sessions.
# ABOUTME: Delegates all asset actions, state semantics, projections, and verification to the task world.

from __future__ import annotations

from typing import Protocol

from aec_bench.contracts.world_session import WorldSessionRequest, WorldSessionResult


class WorldSessionHostError(RuntimeError):
    """Raised when a world-session producer violates the shared host contract."""


class HostWorldSession(Protocol):
    """Minimum session result visible to provider-neutral host orchestration."""

    @property
    def result(self) -> WorldSessionResult: ...


class WorldSessionFactory(Protocol):
    """Task-world producer consumed by the generic session host."""

    task_world_id: str

    def open(self, request: WorldSessionRequest) -> HostWorldSession: ...


def open_world_session(
    request: WorldSessionRequest,
    factory: WorldSessionFactory,
) -> HostWorldSession:
    """Open one task-owned session and validate its shared result binding."""
    if request.task_world_id != factory.task_world_id:
        raise WorldSessionHostError("world-session task identity differs from the selected factory")
    session = factory.open(request)
    result = session.result
    if (
        result.execution_kind,
        result.open_mode,
        result.session_id,
        result.task_world_id,
        result.agent_tenure_id,
    ) != (
        request.execution_kind,
        request.open_mode,
        request.session_id,
        request.task_world_id,
        request.agent_tenure_id,
    ):
        raise WorldSessionHostError("world-session result does not bind the exact request")
    if (
        result.snapshot.run_id,
        result.snapshot.episode_id,
        result.snapshot.world_branch_id,
    ) != (
        request.run_id,
        request.episode_id,
        request.world_branch_id,
    ):
        raise WorldSessionHostError("world-session result belongs to another world")
    if request.start_snapshot is not None and result.snapshot != request.start_snapshot:
        raise WorldSessionHostError("resumed world-session result differs from the requested snapshot")
    return session
