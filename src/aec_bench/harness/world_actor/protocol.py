# ABOUTME: Defines the final versioned local protocol for process-based world actors.
# ABOUTME: Keeps transport correlation and authentication separate from logical action identity.

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, JsonValue

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.harness.world_actor.authority import ActorInvocationOutcomeClass

WORLD_ACTOR_PROTOCOL = "aec-bench/world-actor/1"
WORLD_ACTOR_TRANSPORT_EVIDENCE_SCHEMA = "aec-bench/world-actor-transport-evidence/1"

WORLD_ACTOR_SOCKET_ENV = "AEC_BENCH_WORLD_ACTOR_SOCKET"
WORLD_ACTOR_CAPABILITY_ENV = "AEC_BENCH_WORLD_ACTOR_CAPABILITY_TOKEN"
WORLD_ACTOR_PROTOCOL_ENV = "AEC_BENCH_WORLD_ACTOR_PROTOCOL"


class WorldActorCapabilitiesRequest(FrozenStrictModel):
    """Request the frozen actor capability catalogue."""

    operation: Literal["capabilities"]


class WorldActorObserveRequest(FrozenStrictModel):
    """Request the current actor-visible observation."""

    operation: Literal["observe"]


class WorldActorInvokeRequest(FrozenStrictModel):
    """Request one logical world action under a caller-owned stable identity."""

    operation: Literal["invoke"]
    request_id: NonEmptyStr
    decision_id: NonEmptyStr
    action_name: NonEmptyStr
    arguments: dict[str, JsonValue]


type WorldActorRequest = Annotated[
    WorldActorCapabilitiesRequest | WorldActorObserveRequest | WorldActorInvokeRequest,
    Field(discriminator="operation"),
]


class WorldActorTransportRequest(FrozenStrictModel):
    """One authenticated transport request with version and correlation."""

    protocol: Literal["aec-bench/world-actor/1"]
    transport_request_id: NonEmptyStr
    capability: NonEmptyStr
    request: WorldActorRequest


class WorldActorTransportError(FrozenStrictModel):
    """One safe actor-visible error returned by the endpoint."""

    code: NonEmptyStr
    detail: NonEmptyStr
    retryable: bool
    outcome: ActorInvocationOutcomeClass
    request_id: NonEmptyStr | None = None


class WorldActorTransportSuccess(FrozenStrictModel):
    """A successful response correlated to one transport request."""

    protocol: Literal["aec-bench/world-actor/1"] = "aec-bench/world-actor/1"
    transport_request_id: NonEmptyStr
    ok: Literal[True] = True
    result: dict[str, JsonValue]


class WorldActorTransportFailure(FrozenStrictModel):
    """A failed response correlated to one transport request."""

    protocol: Literal["aec-bench/world-actor/1"] = "aec-bench/world-actor/1"
    transport_request_id: NonEmptyStr
    ok: Literal[False] = False
    error: WorldActorTransportError


type WorldActorTransportResponse = Annotated[
    WorldActorTransportSuccess | WorldActorTransportFailure,
    Field(discriminator="ok"),
]


__all__ = [
    "WORLD_ACTOR_CAPABILITY_ENV",
    "WORLD_ACTOR_PROTOCOL",
    "WORLD_ACTOR_PROTOCOL_ENV",
    "WORLD_ACTOR_SOCKET_ENV",
    "WORLD_ACTOR_TRANSPORT_EVIDENCE_SCHEMA",
    "WorldActorCapabilitiesRequest",
    "WorldActorInvokeRequest",
    "WorldActorObserveRequest",
    "WorldActorRequest",
    "WorldActorTransportError",
    "WorldActorTransportFailure",
    "WorldActorTransportRequest",
    "WorldActorTransportResponse",
    "WorldActorTransportSuccess",
]
