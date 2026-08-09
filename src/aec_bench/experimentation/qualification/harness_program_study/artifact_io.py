# ABOUTME: Publishes and reloads immutable harness-program-study evidence bytes.
# ABOUTME: Centralises repository confinement, collision, digest, and JSON error translation.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.ledger.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifact,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
    ImmutableArtifactStore,
)


def _publish_experiment_bytes(
    *,
    root: Path,
    relative_path: str,
    encoded: bytes,
    label: str,
) -> ImmutableArtifact:
    try:
        repository = EvidenceRepository(Path(root))
        return repository.publish_bytes(relative_path, encoded)
    except ImmutableArtifactCollisionError as error:
        raise ValueError(
            f"{label} path already contains different content",
        ) from error
    except (
        ImmutableArtifactConfinementError,
        ImmutableArtifactIntegrityError,
    ) as error:
        raise ValueError(f"invalid {label} repository: {error}") from error


def _verify_artifact(artifact: ArtifactReference) -> None:
    path = Path(artifact.path)
    try:
        _artifact_store(path).load_bytes(
            path.name,
            expected_sha256=artifact.sha256,
        )
    except ImmutableArtifactIntegrityError as error:
        if "digest mismatch" in str(error):
            raise ValueError(
                f"harness-program-study artifact digest mismatch: {path}",
            ) from error
        raise ValueError(
            f"harness-program-study evidence artifact is missing: {path}",
        ) from error
    except ImmutableArtifactConfinementError as error:
        raise ValueError(
            f"harness-program-study artifact digest mismatch: {path}",
        ) from error


def _read_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(_load_path_bytes(path, label=label))
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"invalid {label}: expected a JSON object")
    return payload


def _sha256_path(path: Path) -> str:
    try:
        return _artifact_store(path).reference(path.name).sha256
    except (
        ImmutableArtifactConfinementError,
        ImmutableArtifactIntegrityError,
    ) as error:
        raise ValueError(f"harness-program-study evidence artifact is missing: {path}") from error


def _load_path_bytes(path: Path, *, label: str) -> bytes:
    try:
        return _artifact_store(path).load_bytes(path.name)
    except (
        ImmutableArtifactConfinementError,
        ImmutableArtifactIntegrityError,
    ) as error:
        raise ValueError(f"invalid {label}: {path}") from error


def _artifact_store(path: Path) -> ImmutableArtifactStore:
    parent = Path(path).parent
    if not parent.is_dir():
        raise ImmutableArtifactIntegrityError(
            f"immutable artifact parent is missing: {parent}",
        )
    return ImmutableArtifactStore(parent)


def _pretty_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
