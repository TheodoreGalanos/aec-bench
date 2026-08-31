# ABOUTME: Defines provider-neutral actor invocation values and the authority port.
# ABOUTME: Keeps adapters independent from the harness implementation of world authority.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from pydantic import Field, JsonValue

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.contracts.world_interface import (
    WorldActorActionResult,
    WorldActorCapabilityCatalogue,
    WorldActorObservation,
)

ACTOR_INVOCATION_SEMANTICS = "aec-bench/actor-invocation/1"


class ActorInvocationOutcomeClass(StrEnum):
    """State whether a world action was not dispatched, completed, or is unknown."""

    NOT_DISPATCHED = "not-dispatched"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


class ActorTurnDisposition(StrEnum):
    """Tell a provider-neutral actor loop whether the current turn can continue."""

    CONTINUE = "continue"
    CONCLUDE_TURN = "conclude-turn"


class ActorCorrelation(FrozenStrictModel):
    """Token-free transport correlation that does not participate in request identity."""

    transport_request_id: NonEmptyStr | None = None
    provider_session_id: NonEmptyStr | None = None
    provider_tool_call_id: NonEmptyStr | None = None
    model_turn: int | None = Field(default=None, ge=1)


class ActorInvocationRequest(FrozenStrictModel):
    """One transport-neutral logical world action request."""

    request_id: NonEmptyStr
    decision_id: NonEmptyStr
    action_name: NonEmptyStr
    arguments: dict[str, JsonValue]
    transport: NonEmptyStr
    correlation: ActorCorrelation


@dataclass(frozen=True)
class ActorInvocationOutcome:
    """One completed world action outcome returned by the shared authority."""

    result: WorldActorActionResult
    action_sequence: int
    duplicate: bool
    disposition: ActorTurnDisposition


class ActorInvocationError(RuntimeError):
    """A stable actor-boundary failure that transports can render without interpretation."""

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        outcome: ActorInvocationOutcomeClass,
        request_id: str | None = None,
        action_sequence: int | None = None,
        duplicate: bool = False,
        disposition: ActorTurnDisposition = ActorTurnDisposition.CONTINUE,
    ) -> None:
        self.code = code
        self.detail = detail
        self.outcome = outcome
        self.request_id = request_id
        self.action_sequence = action_sequence
        self.duplicate = duplicate
        self.disposition = disposition
        super().__init__(f"{code}: {detail}")


class ActorInvocationAuthorityPort(Protocol):
    """The authority operations required by a provider adapter."""

    @property
    def catalogue_hash(self) -> str | None: ...

    @property
    def terminal(self) -> bool: ...

    def capabilities(self, *, correlation: ActorCorrelation) -> WorldActorCapabilityCatalogue: ...

    def observe(self, *, correlation: ActorCorrelation) -> WorldActorObservation: ...

    def invoke(self, request: ActorInvocationRequest) -> ActorInvocationOutcome: ...


def canonical_actor_catalogue(catalogue: WorldActorCapabilityCatalogue) -> dict[str, Any]:
    """Return the task catalogue with a stable action order and canonical JSON values."""

    return {
        "task_world_id": catalogue.task_world_id,
        "actions": [
            action.model_dump(mode="json") for action in sorted(catalogue.actions, key=lambda action: action.name)
        ],
    }


def actor_catalogue_sha256(catalogue: WorldActorCapabilityCatalogue) -> str:
    """Return one transport-neutral identity for a frozen actor catalogue."""

    payload = json.dumps(canonical_actor_catalogue(catalogue), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = (
    "ACTOR_INVOCATION_SEMANTICS",
    "ActorCorrelation",
    "ActorInvocationAuthorityPort",
    "ActorInvocationError",
    "ActorInvocationOutcome",
    "ActorInvocationOutcomeClass",
    "ActorInvocationRequest",
    "ActorTurnDisposition",
    "actor_catalogue_sha256",
    "canonical_actor_catalogue",
)
