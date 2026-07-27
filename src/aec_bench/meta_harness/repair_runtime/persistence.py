# ABOUTME: Owns content-addressed repair artifact wrappers and filesystem verification helpers.
# ABOUTME: Keeps persisted evidence byte checks separate from repair interpretation and orchestration.

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.evolution.repair_loop import RepairLoopResult
from aec_bench.meta_harness.authority_ledger import StoredAuthorityEvent


@dataclass(frozen=True)
class StoredRepairArtifact:
    """Physical content-pinned artifact plus the TrialRecord-compatible reference."""

    path: Path
    reference: ArtifactReference


@dataclass(frozen=True)
class StoredRepairRunArtifact:
    """Physical run artifact addressable by repair and candidate lineage."""

    run_id: str
    candidate_id: str
    path: Path
    reference: ArtifactReference


@dataclass(frozen=True)
class RepairRuntimeExecution:
    """Closed loop result together with its persistent plan, run, and terminal artifacts."""

    result: RepairLoopResult
    attempt_plan: StoredRepairArtifact
    run_artifacts: tuple[StoredRepairRunArtifact, ...]
    terminal: StoredRepairArtifact
    authority_event: StoredAuthorityEvent | None = None
    authority_error: str | None = None


def _file_reference(path: Path) -> ArtifactReference:
    return ArtifactReference(
        kind="trial-record",
        path=str(path),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        media_type="application/json",
    )


def _artifact_identity(reference: ArtifactReference) -> tuple[str, str]:
    return str(Path(reference.path).resolve()), reference.sha256


def _verify_artifact_reference(reference: ArtifactReference, *, label: str) -> None:
    path = Path(reference.path)
    if not path.is_file():
        raise ValueError(f"{label} artifact is missing")
    if hashlib.sha256(path.read_bytes()).hexdigest() != reference.sha256:
        raise ValueError(f"{label} artifact hash mismatch")


def _write_content_addressed(path: Path, encoded: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("content-addressed repair artifact path contains different bytes")
    if not path.exists():
        path.write_bytes(encoded)
