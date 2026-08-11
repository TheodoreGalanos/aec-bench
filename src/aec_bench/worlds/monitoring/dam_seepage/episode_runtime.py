# ABOUTME: Exposes the dam seepage task through the shared live episode and actor contracts.
# ABOUTME: Keeps Prime transport, evaluation, and provider behavior outside the monitoring world.

from __future__ import annotations

import threading
from typing import cast

from pydantic import JsonValue, TypeAdapter

from aec_bench.contracts.world_interface import (
    WorldActorActionCapability,
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldActorCapabilityCatalogue,
    WorldActorObservation,
    WorldInterfaceError,
)
from aec_bench.worlds.monitoring.dam_seepage.definition import DamSeepageProfile
from aec_bench.worlds.monitoring.dam_seepage.world import (
    DAM_SEEPAGE_TASK_WORLD_ID,
    SeepageAction,
    SeepageActionResult,
    SeepageObservation,
    SeepageState,
    available_actions,
    observe,
    transition,
)
from aec_bench.worlds.runtime.episode import (
    ActionSubmission,
    Decision,
    Episode,
    EpisodeFinishedError,
    EpisodeFunctions,
    EpisodeStatus,
    MemoryEpisodeRecorder,
)

_OBSERVATION_ADAPTER = TypeAdapter(SeepageObservation)
_EMPTY_ARGUMENTS_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
_ACTION_DESCRIPTIONS = {
    SeepageAction.RECORD_CONFIRMATION_READING: "Release the next scheduled seepage reading.",
    SeepageAction.CHECK_MEASUREMENT_SYSTEM: "Release the current measurement-system condition.",
    SeepageAction.INSPECT_DOWNSTREAM_AREA: "Release the downstream condition for the current reading.",
    SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW: "Submit escalation for engineering review.",
    SeepageAction.CONTINUE_ROUTINE_SURVEILLANCE: "Submit continued routine surveillance.",
}


class DamSeepageEpisodeHost:
    """Own one bounded dam seepage episode behind the installed actor models."""

    def __init__(
        self,
        *,
        profile: DamSeepageProfile,
        episode_id: str = "dam-seepage-episode",
        actor_id: str = "prime-composite-actor",
    ) -> None:
        self._recorder = MemoryEpisodeRecorder[
            SeepageState,
            SeepageObservation,
            SeepageAction,
            SeepageActionResult,
        ]()
        self._episode = Episode[
            SeepageState,
            SeepageObservation,
            SeepageAction,
            SeepageActionResult,
            tuple[SeepageAction, ...],
        ](
            episode_id=episode_id,
            actor_id=actor_id,
            state=profile.opening_state,
            functions=EpisodeFunctions(
                observe=observe,
                transition=transition,
                available_actions=available_actions,
            ),
            recorder=self._recorder,
        )
        self._requests: dict[str, tuple[str, WorldActorActionResult]] = {}
        self._lock = threading.Lock()
        self._last_action_result: WorldActorActionResult | None = None

    @property
    def state(self) -> SeepageState:
        return self._episode.state

    @property
    def status(self) -> EpisodeStatus:
        return self._episode.status

    @property
    def recorder(
        self,
    ) -> MemoryEpisodeRecorder[SeepageState, SeepageObservation, SeepageAction, SeepageActionResult]:
        return self._recorder

    @property
    def last_action_result(self) -> WorldActorActionResult | None:
        return self._last_action_result

    def capabilities(self) -> WorldActorCapabilityCatalogue:
        """Return only the five task-owned monitoring actions."""
        return WorldActorCapabilityCatalogue(
            task_world_id=DAM_SEEPAGE_TASK_WORLD_ID,
            actions=tuple(
                WorldActorActionCapability(
                    name=action.value,
                    description=_ACTION_DESCRIPTIONS[action],
                    input_schema=_EMPTY_ARGUMENTS_SCHEMA,
                )
                for action in SeepageAction
            ),
        )

    def observe(self) -> WorldActorObservation:
        """Return the current actor-visible monitoring evidence."""
        with self._lock:
            return _actor_observation(self._current_decision())

    def invoke(self, request: WorldActorActionRequest) -> WorldActorActionResult:
        """Apply one exact actor request and preserve safe retry semantics."""
        fingerprint = request.model_dump_json()
        with self._lock:
            previous = self._requests.get(request.request_id)
            if previous is not None:
                if previous[0] != fingerprint:
                    raise WorldInterfaceError(
                        "actor-request-id-conflict",
                        f"{request.request_id} is already bound to different content",
                    )
                return previous[1]
            if request.arguments:
                raise WorldInterfaceError(
                    "actor-action-arguments",
                    f"{request.action_name} accepts no arguments",
                )
            try:
                action = SeepageAction(request.action_name)
            except ValueError as error:
                raise WorldInterfaceError("unknown-actor-action", request.action_name) from error

            self._current_decision()
            reply = self._episode.submit(
                ActionSubmission(
                    decision_id=request.decision_id,
                    action=action,
                )
            )
            if reply.rejection is not None:
                result = WorldActorActionResult(
                    request_id=request.request_id,
                    action_name=request.action_name,
                    status="rejected",
                    task_receipt={
                        "code": reply.rejection.code,
                        "message": reply.rejection.message,
                    },
                    next_observation=(_actor_observation(reply.decision) if reply.decision is not None else None),
                    terminated=reply.terminated,
                    truncated=reply.truncated,
                    reason=reply.reason,
                )
            else:
                if not reply.accepted or reply.output is None:
                    raise WorldInterfaceError("world-action-failed", reply.reason or "world action was not accepted")
                result = WorldActorActionResult(
                    request_id=request.request_id,
                    action_name=request.action_name,
                    status="applied",
                    task_receipt={
                        "code": "action-applied",
                        "message": reply.output.detail,
                    },
                    next_observation=(_actor_observation(reply.decision) if reply.decision is not None else None),
                    terminated=reply.terminated,
                    truncated=reply.truncated,
                    reason=reply.reason,
                )
            self._requests[request.request_id] = (fingerprint, result)
            self._last_action_result = result
            return result

    def _current_decision(self) -> Decision[SeepageObservation, tuple[SeepageAction, ...]]:
        try:
            return self._episode.current_decision()
        except EpisodeFinishedError as error:
            raise WorldInterfaceError("world-finished", str(error)) from error


def _actor_observation(
    decision: Decision[SeepageObservation, tuple[SeepageAction, ...]],
) -> WorldActorObservation:
    payload = _OBSERVATION_ADAPTER.dump_python(decision.observation, mode="json")
    if not isinstance(payload, dict):
        raise RuntimeError("dam seepage observation did not serialize to an object")
    return WorldActorObservation(
        decision_id=decision.decision_id,
        view=cast(dict[str, JsonValue], payload),
    )


__all__ = ["DamSeepageEpisodeHost"]
