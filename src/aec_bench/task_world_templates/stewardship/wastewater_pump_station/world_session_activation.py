# ABOUTME: Defines immutable V4 session activation bindings and their active selector.
# ABOUTME: Binds host authority and tenure context to one exact durable world snapshot.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.contracts.harness_kernel import validate_sha256

PUMP_STATION_SESSION_ACTIVATION_BINDING_VERSION = "pump-station.session-activation-binding.v1"
PUMP_STATION_SESSION_ACTIVATION_CLAIM_VERSION = "pump-station.session-activation-claim.v1"
PUMP_STATION_ACTIVE_SESSION_POINTER_VERSION = "pump-station.active-session-pointer.v1"


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_sha256(value: str, field_name: str) -> None:
    try:
        validate_sha256(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a SHA-256 digest") from error


@dataclass(frozen=True, slots=True)
class PumpStationSessionActivationBinding:
    """One host-approved session tenure bound to an exact V4 world position."""

    binding_version: str
    active_activation_id: str
    run_id: str
    episode_id: str
    world_branch_id: str
    state_id: str
    commit_id: str
    sequence: int
    session_id: str
    agent_tenure_id: str
    actor_view_id: str
    information_set_manifest_content_id: str
    retrieval_state_head: str
    prior_binding_id: str | None
    session_event_sequence: int
    host_authority_id: str

    def __post_init__(self) -> None:
        if self.binding_version != PUMP_STATION_SESSION_ACTIVATION_BINDING_VERSION:
            raise ValueError("unsupported pump-station session activation binding version")
        for field_name in (
            "active_activation_id",
            "run_id",
            "episode_id",
            "world_branch_id",
            "session_id",
            "agent_tenure_id",
            "host_authority_id",
        ):
            _require_text(getattr(self, field_name), field_name)
        for field_name in (
            "state_id",
            "commit_id",
            "actor_view_id",
            "information_set_manifest_content_id",
            "retrieval_state_head",
        ):
            _require_sha256(getattr(self, field_name), field_name)
        if self.prior_binding_id is not None:
            _require_sha256(self.prior_binding_id, "prior_binding_id")
        if self.sequence < 0:
            raise ValueError("session activation world sequence must be non-negative")
        if self.session_event_sequence < 0:
            raise ValueError("session activation event sequence must be non-negative")
        if self.session_event_sequence == 0 and self.prior_binding_id is not None:
            raise ValueError("initial session activation must not name a prior binding")
        if self.session_event_sequence > 0 and self.prior_binding_id is None:
            raise ValueError("replacement session activation requires a prior binding")

    @property
    def binding_id(self) -> str:
        """Return the canonical content identity of this immutable binding."""

        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
            pump_station_artifact_id,
        )

        return pump_station_artifact_id(self, record_profile="v4")


@dataclass(frozen=True, slots=True)
class PumpStationSessionActivationClaim:
    """Immutable claim that one activation identity selects one binding."""

    claim_version: str
    active_activation_id: str
    binding_id: str

    def __post_init__(self) -> None:
        if self.claim_version != PUMP_STATION_SESSION_ACTIVATION_CLAIM_VERSION:
            raise ValueError("unsupported pump-station session activation claim version")
        _require_text(self.active_activation_id, "active_activation_id")
        _require_sha256(self.binding_id, "binding_id")


@dataclass(frozen=True, slots=True)
class PumpStationActiveSessionPointer:
    """Atomic selector for the active immutable V4 session binding."""

    pointer_version: str
    run_id: str
    episode_id: str
    world_branch_id: str
    active_activation_id: str
    active_binding_id: str
    session_event_sequence: int

    def __post_init__(self) -> None:
        if self.pointer_version != PUMP_STATION_ACTIVE_SESSION_POINTER_VERSION:
            raise ValueError("unsupported pump-station active session pointer version")
        for field_name in (
            "run_id",
            "episode_id",
            "world_branch_id",
            "active_activation_id",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_sha256(self.active_binding_id, "active_binding_id")
        if self.session_event_sequence < 0:
            raise ValueError("active session pointer sequence must be non-negative")


__all__ = [
    "PUMP_STATION_ACTIVE_SESSION_POINTER_VERSION",
    "PUMP_STATION_SESSION_ACTIVATION_BINDING_VERSION",
    "PUMP_STATION_SESSION_ACTIVATION_CLAIM_VERSION",
    "PumpStationActiveSessionPointer",
    "PumpStationSessionActivationBinding",
    "PumpStationSessionActivationClaim",
]
