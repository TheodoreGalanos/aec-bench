# ABOUTME: Defines Morph proposal boundary phases, immutable receipts, and provider state.
# ABOUTME: Keeps lifecycle identity contracts independent from Harbor orchestration and I/O.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ProposalMorphBoundaryError(RuntimeError):
    """Reject an operation that could cross the proposal isolation boundary."""


class BoundaryPhase(StrEnum):
    """Host-owned lifecycle phases for one proposal environment."""

    NEW = "new"
    CANDIDATE = "candidate"
    ROTATING = "rotating"
    VERIFIER = "verifier"
    BROKEN = "broken"
    CLOSED = "closed"


class HandoffVariant(StrEnum):
    """Allowlisted evidence shapes crossing from candidate to verifier."""

    COMPLETED_OUTPUT = "completed_output"
    CANDIDATE_FAILURE = "candidate_failure"


@dataclass
class ProposalMorphState:
    """Mutable provider handles owned only by the environment state machine."""

    snapshot: object
    instance: object
    container_identity: str


@dataclass(frozen=True)
class ProposalCandidateInvocationTransition:
    """Auditable host receipt for one candidate-container replacement."""

    invocation_id: str
    previous_container_identity: str
    current_container_identity: str
    runtime_archive_sha256: str
    receipt_path: Path

    @property
    def container_identity(self) -> str:
        """Compatibility alias for callers that predate the explicit current name."""

        return self.current_container_identity


@dataclass(frozen=True)
class ProposalMorphCleanupReceipt:
    """Validated proof that one verifier environment was destructively removed."""

    receipt_path: Path
    receipt_sha256: str
    content_sha256: str
    runtime_archive_sha256: str
    runtime_archive_content_sha256: str
    runtime_snapshot_identity: str
    trial_instance_identity: str
    rotation_receipt_sha256: str
    rotation_receipt_content_sha256: str
    verifier_container_identity: str
    handoff_variant: str = HandoffVariant.COMPLETED_OUTPUT.value
    candidate_failure_session_receipt_sha256: str | None = None


@dataclass(frozen=True)
class TestsSnapshot:
    """Pinned verifier-test tree and its mode-sensitive content identity."""

    path: Path
    content_sha256: str


@dataclass(frozen=True)
class SealedArtifact:
    """One host-captured candidate artifact with immutable byte identity."""

    path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class SealedHandoff:
    """Validated set of evidence allowed to cross into the verifier phase."""

    artifacts: dict[str, SealedArtifact]
    variant: HandoffVariant
    candidate_failure_session_receipt_sha256: str | None


@dataclass(frozen=True)
class VerifierRotationBinding:
    """Verified content and container identities from a completed rotation."""

    receipt_sha256: str
    receipt_content_sha256: str
    verifier_container_identity: str
    handoff_variant: HandoffVariant
    candidate_failure_session_receipt_sha256: str | None
