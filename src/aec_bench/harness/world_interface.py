# ABOUTME: Validates task-neutral actor calls at the provider-independent host boundary.
# ABOUTME: Leaves action fields, projections, state changes, and verification with each task world.

from __future__ import annotations

from typing import Protocol

from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldActorCapabilityCatalogue,
    WorldActorObservation,
    WorldInterfaceError,
)
from aec_bench.contracts.world_session import WorldSessionResult


class ActorWorldSession(Protocol):
    """Supported actor contract implemented by one task-owned live session."""

    @property
    def result(self) -> WorldSessionResult: ...

    @property
    def actor_capabilities(self) -> WorldActorCapabilityCatalogue: ...

    def observe_actor(self) -> WorldActorObservation: ...

    def invoke_actor_action(
        self,
        request: WorldActorActionRequest,
    ) -> WorldActorActionResult: ...


def _validate_observation(
    session: ActorWorldSession,
    observation: WorldActorObservation,
) -> None:
    result = session.result
    binding = observation.binding
    if (
        binding.task_world_id,
        binding.session_id,
        binding.run_id,
        binding.episode_id,
        binding.world_branch_id,
        binding.agent_tenure_id,
    ) != (
        result.task_world_id,
        result.session_id,
        result.snapshot.run_id,
        result.snapshot.episode_id,
        result.snapshot.world_branch_id,
        result.agent_tenure_id,
    ):
        raise WorldInterfaceError(
            "actor-observation-binding-invalid",
            "actor observation belongs to another session or world",
        )
    if (
        binding.sequence,
        binding.state_id,
        binding.commit_id,
        binding.actor_view_id,
        binding.information_set_id,
    ) != (
        result.snapshot.sequence,
        result.snapshot.state_id,
        result.snapshot.commit_id,
        result.actor_view_id,
        result.information_set_id,
    ):
        raise WorldInterfaceError(
            "actor-observation-state-invalid",
            "actor observation differs from the current public session result",
        )


def observe_world_actor(session: ActorWorldSession) -> WorldActorObservation:
    """Return and validate the task-owned current actor observation."""

    observation = session.observe_actor()
    _validate_observation(session, observation)
    return observation


def invoke_world_actor(
    session: ActorWorldSession,
    request: WorldActorActionRequest,
) -> WorldActorActionResult:
    """Invoke one task-owned action and validate its public post-state binding."""

    if request.action_name not in {item.name for item in session.actor_capabilities.actions}:
        raise WorldInterfaceError(
            "actor-action-unavailable",
            request.action_name,
        )
    result = session.invoke_actor_action(request)
    if result.request_content_sha256 != request.content_sha256:
        raise WorldInterfaceError(
            "actor-result-request-invalid",
            "actor result does not bind the exact request",
        )
    if result.pre_binding != request.binding:
        raise WorldInterfaceError(
            "actor-result-pre-binding-invalid",
            "actor result does not preserve the requested binding",
        )
    _validate_observation(session, result.next_observation)
    if result.post_binding != result.next_observation.binding:
        raise WorldInterfaceError(
            "actor-result-post-binding-invalid",
            "actor result and next observation bindings differ",
        )
    return result
