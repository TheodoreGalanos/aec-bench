# ABOUTME: Exposes the provider-neutral actor invocation authority for interactive worlds.
# ABOUTME: Keeps world action semantics independent from Prime, DeepSeek, and transport framing.

from aec_bench.harness.world_actor.authority import (
    ACTOR_INVOCATION_EVIDENCE_SCHEMA,
    ACTOR_INVOCATION_SEMANTICS,
    ActorCorrelation,
    ActorInvocationAuthority,
    ActorInvocationAuthorityConfig,
    ActorInvocationError,
    ActorInvocationLifecycle,
    ActorInvocationOutcome,
    ActorInvocationOutcomeClass,
    ActorInvocationRequest,
    ActorTurnDisposition,
    AuthorityCloseReport,
    WorldActorHost,
    actor_catalogue_sha256,
    canonical_actor_catalogue,
)
from aec_bench.harness.world_actor.client_bundle import (
    InstalledClient,
    WorldActorClientInstallError,
    install_world_actor_client,
)
from aec_bench.harness.world_actor.endpoint import (
    WorldActorEndpoint,
    WorldActorEndpointCloseReport,
    WorldActorEndpointError,
    WorldActorEndpointLifecycle,
)
from aec_bench.harness.world_actor.protocol import (
    WORLD_ACTOR_CAPABILITY_ENV,
    WORLD_ACTOR_PROTOCOL,
    WORLD_ACTOR_PROTOCOL_ENV,
    WORLD_ACTOR_SOCKET_ENV,
)

__all__ = [
    "ACTOR_INVOCATION_EVIDENCE_SCHEMA",
    "ACTOR_INVOCATION_SEMANTICS",
    "ActorCorrelation",
    "ActorInvocationAuthority",
    "ActorInvocationAuthorityConfig",
    "ActorInvocationError",
    "ActorInvocationLifecycle",
    "ActorInvocationOutcome",
    "ActorInvocationOutcomeClass",
    "ActorInvocationRequest",
    "ActorTurnDisposition",
    "AuthorityCloseReport",
    "InstalledClient",
    "WORLD_ACTOR_CAPABILITY_ENV",
    "WORLD_ACTOR_PROTOCOL",
    "WORLD_ACTOR_PROTOCOL_ENV",
    "WORLD_ACTOR_SOCKET_ENV",
    "WorldActorClientInstallError",
    "WorldActorEndpoint",
    "WorldActorEndpointCloseReport",
    "WorldActorEndpointError",
    "WorldActorEndpointLifecycle",
    "WorldActorHost",
    "actor_catalogue_sha256",
    "canonical_actor_catalogue",
    "install_world_actor_client",
]
