# ABOUTME: Persists and verifies canonical adaptive-cycle JSON artifacts.
# ABOUTME: Centralizes exact bytes, content-addressed paths, and digest evidence.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.contracts import (
    AdaptiveCycleReport,
)


def write_cycle_report(report: AdaptiveCycleReport, *, root: Path) -> Path:
    """Persist a top-level report at its content-addressed canonical path."""

    reference = write_json_artifact(
        report.model_dump(mode="json"),
        identity=report.content_sha256,
        root=root / "adaptive-cycles",
        filename="adaptive-cycle-report.json",
        kind="adaptive-cycle-report",
    )
    return Path(reference.path)


def write_json_artifact(
    payload: dict[str, object],
    *,
    identity: str,
    root: Path,
    filename: str,
    kind: str,
) -> ArtifactReference:
    """Write exact sorted JSON bytes or accept an identical existing artifact."""

    validate_sha256(identity)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    path = Path(root) / identity / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError(f"content-addressed adaptive artifact already contains different bytes: {path}")
    if not path.exists():
        path.write_bytes(encoded)
    return ArtifactReference(
        kind=kind,
        path=str(path),
        sha256=hashlib.sha256(encoded).hexdigest(),
        media_type="application/json",
    )


def artifact_reference(path: Path, *, kind: str) -> ArtifactReference:
    """Bind an existing JSON artifact to its exact digest."""

    source = Path(path)
    return ArtifactReference(
        kind=kind,
        path=str(source),
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        media_type="application/json",
    )


def verify_artifact(reference: ArtifactReference) -> None:
    """Fail closed when a referenced adaptive-cycle artifact is absent or changed."""

    path = Path(reference.path)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != reference.sha256:
        raise ValueError(f"adaptive cycle artifact digest mismatch: {reference.path}")
