# ABOUTME: Defines safe persisted evidence and recovery state for Prime pump journeys.
# ABOUTME: Stores only coordination and canonical references, never hidden world or host-control content.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.contracts.world_session import StewardshipStateSnapshotRef, WorldSessionOpenMode, WorldSessionRequest
from aec_bench.harness.pump_station_prime.session import PumpStationPrimeSessionLimits
from aec_bench.ledger.durability import DurableFileReplaceError, replace_file_bytes_durable
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.refinement import PrimeRefinementCandidate, PrimeRefinementMode
from aec_bench.prime_agent.session_evidence import PrimeAcpUsage

CHECKPOINT_NAME = "prime-world-journey-checkpoint.json"
RUN_NAME = "prime-world-journey.json"
type PumpStationPrimeJourneyPhase = Literal["ready", "running", "segment_ended", "control_pending", "finished"]


class PumpStationPrimeJourneyRecoveryError(RuntimeError):
    """Raised when saved journey coordination cannot be resumed safely."""


@dataclass(frozen=True, slots=True)
class PumpStationPrimeJourneyLimits:
    """Private safety limits for one complete Prime journey."""

    max_sessions: int
    max_host_controls: int
    max_world_actions: int
    max_model_calls: int
    max_tokens: int
    max_cost_usd: Decimal
    max_wall_seconds: float

    def __post_init__(self) -> None:
        if self.max_sessions < 1:
            raise ValueError("Prime journey max_sessions must be positive")
        if self.max_host_controls < 1:
            raise ValueError("Prime journey max_host_controls must be positive")
        PumpStationPrimeSessionLimits(
            max_world_actions=self.max_world_actions,
            max_model_calls=self.max_model_calls,
            max_tokens=self.max_tokens,
            max_cost_usd=self.max_cost_usd,
            max_wall_seconds=self.max_wall_seconds,
        )


class PumpStationPrimeJourneySegment(FrozenStrictModel):
    """Safe evidence for one closed Prime session in a journey."""

    index: int
    world_session_id: NonEmptyStr
    prime_session_id: str | None
    open_mode: WorldSessionOpenMode
    start_snapshot: StewardshipStateSnapshotRef
    end_snapshot: StewardshipStateSnapshotRef
    prime_run: NonEmptyStr
    world_run: NonEmptyStr
    session_state: NonEmptyStr
    stop_reason: str | None
    limit_reason: str | None
    completion: NonEmptyStr
    usage: PrimeAcpUsage
    elapsed_seconds: float
    world_action_attempts: int
    world_action_limit_reached: bool
    benchmark_valid: bool
    refinement_mode: PrimeRefinementMode
    refinement_candidate_sha256: NonEmptyStr
    refinement_global_candidate_sha256: NonEmptyStr
    refinement_changed: bool
    refinement_portable: bool
    refinement_issues: tuple[NonEmptyStr, ...]


class PumpStationPrimeJourneyControl(FrozenStrictModel):
    """Canonical host-control lineage without hidden control content."""

    index: int
    request_id: NonEmptyStr
    operation: NonEmptyStr
    parent_snapshot: StewardshipStateSnapshotRef
    result_snapshot: StewardshipStateSnapshotRef


class PumpStationPrimeJourneyCheckpoint(FrozenStrictModel):
    """Private current coordination state; the world repository remains causal authority."""

    config_id: NonEmptyStr
    journey_id: NonEmptyStr
    host_policy_sha256: NonEmptyStr
    started_at: datetime
    phase: PumpStationPrimeJourneyPhase
    next_session: WorldSessionRequest | None
    refinement_candidate: PrimeRefinementCandidate | None = None
    finished_at: datetime | None = None
    pending_request_id: str | None = None
    pending_parent: StewardshipStateSnapshotRef | None = None
    segments: tuple[PumpStationPrimeJourneySegment, ...] = ()
    host_controls: tuple[PumpStationPrimeJourneyControl, ...] = ()
    completion: str | None = None
    world_state: str | None = None
    stop_reason: str | None = None


def journey_config_id(
    *,
    session_request: WorldSessionRequest,
    instruction: str,
    model: str,
    isolation: PrimeAcpIsolation,
    limits: PumpStationPrimeJourneyLimits,
    guided: bool,
    refinement_mode: PrimeRefinementMode,
    refinement_candidate: PrimeRefinementCandidate | None,
    executable: str,
    host_policy_sha256: str,
) -> str:
    payload = {
        "session": session_request.model_dump(mode="json"),
        "instruction_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        "model": model,
        "isolation": isolation,
        "limits": limit_payload(limits),
        "guided": guided,
        "refinement_mode": refinement_mode,
        "refinement_candidate_sha256": (None if refinement_candidate is None else refinement_candidate.content_sha256),
        "executable": executable,
        "host_policy_sha256": host_policy_sha256,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def elapsed_seconds(checkpoint: PumpStationPrimeJourneyCheckpoint) -> float:
    end = checkpoint.finished_at or datetime.now(UTC)
    return max(0.0, (end - checkpoint.started_at).total_seconds())


def limit_payload(limits: PumpStationPrimeJourneyLimits) -> dict[str, int | float | str]:
    return {
        "max_sessions": limits.max_sessions,
        "max_host_controls": limits.max_host_controls,
        "max_world_actions": limits.max_world_actions,
        "max_model_calls": limits.max_model_calls,
        "max_tokens": limits.max_tokens,
        "max_cost_usd": str(limits.max_cost_usd),
        "max_wall_seconds": limits.max_wall_seconds,
    }


def read_checkpoint(path: Path, config_id: str) -> PumpStationPrimeJourneyCheckpoint:
    if not path.is_file():
        raise PumpStationPrimeJourneyRecoveryError("Prime journey checkpoint does not exist")
    try:
        checkpoint = PumpStationPrimeJourneyCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise PumpStationPrimeJourneyRecoveryError("Prime journey checkpoint is invalid") from error
    if checkpoint.config_id != config_id:
        raise PumpStationPrimeJourneyRecoveryError("Prime journey resume configuration differs from its checkpoint")
    if [segment.index for segment in checkpoint.segments] != list(range(len(checkpoint.segments))):
        raise PumpStationPrimeJourneyRecoveryError("Prime journey segment order is invalid")
    if [control.index for control in checkpoint.host_controls] != list(range(len(checkpoint.host_controls))):
        raise PumpStationPrimeJourneyRecoveryError("Prime journey host-control order is invalid")
    if checkpoint.phase in {"ready", "running"} and checkpoint.next_session is None:
        raise PumpStationPrimeJourneyRecoveryError("Prime journey checkpoint has no next session")
    if checkpoint.phase == "control_pending" and (
        checkpoint.pending_request_id is None or checkpoint.pending_parent is None
    ):
        raise PumpStationPrimeJourneyRecoveryError("Prime journey checkpoint has no pending host control")
    if checkpoint.phase != "control_pending" and (
        checkpoint.pending_request_id is not None or checkpoint.pending_parent is not None
    ):
        raise PumpStationPrimeJourneyRecoveryError("Prime journey checkpoint has an unexpected pending host control")
    if checkpoint.phase == "finished" and None in (
        checkpoint.finished_at,
        checkpoint.completion,
        checkpoint.world_state,
        checkpoint.stop_reason,
    ):
        raise PumpStationPrimeJourneyRecoveryError("Prime journey finished checkpoint is incomplete")
    return checkpoint


def write_checkpoint(path: Path, checkpoint: PumpStationPrimeJourneyCheckpoint) -> None:
    atomic_write_json(path, checkpoint.model_dump(mode="json"))


def atomic_write_json(path: Path, payload: object) -> None:
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        replace_file_bytes_durable(path.parent, path.name, encoded, host_private=True)
    except DurableFileReplaceError as error:
        raise PumpStationPrimeJourneyRecoveryError("Prime journey evidence could not be written durably") from error
