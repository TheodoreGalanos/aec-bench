# ABOUTME: Persists and reopens immutable proposal import artifacts in EvidenceRepository.
# ABOUTME: Preserves canonical bytes, physical hashes, and confinement errors.

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import TypeAdapter

from aec_bench.contracts.harness_kernel import FrozenStrictModel
from aec_bench.contracts.proposal_execution.session import ProposalSessionReceipt
from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.experimentation.proposals.harbor_import import ProposalHarborImportEvidence
from aec_bench.experimentation.proposals.proposal_dispatch import (
    GovernedProposalDispatchAuthorization,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.contracts import (
    ProposalTrialImportError,
)
from aec_bench.ledger.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
    validate_evidence_root,
)
from aec_bench.ledger.reader import read_trial_record
from aec_bench.ledger.writer import DuplicateTrialRecordError, write_trial_record


def snapshot_evidence_artifacts(
    *,
    repository: EvidenceRepository,
    evidence: ProposalHarborImportEvidence,
    repo_root: Path,
    object_root: Path,
) -> tuple[
    list[ArtifactReference],
    dict[tuple[str, str, str], ArtifactReference],
]:
    """Copy every proposal session artifact into the immutable repository."""
    copied = [
        snapshot_file(
            repository=repository,
            reference=artifact,
            repo_root=repo_root,
            object_root=object_root,
        )
        for artifact in evidence.artifacts
    ]
    by_identity = {
        (source.kind, source.path, source.sha256): target
        for source, target in zip(evidence.artifacts, copied, strict=True)
    }
    return copied, by_identity


def copied_artifact(
    source: ArtifactReference,
    copied: dict[tuple[str, str, str], ArtifactReference],
) -> ArtifactReference:
    """Resolve one source artifact to its preserved immutable copy."""
    try:
        return copied[(source.kind, source.path, source.sha256)]
    except KeyError as error:
        raise ProposalTrialImportError(
            f"bound proposal artifact was not preserved: {source.kind}",
        ) from error


def snapshot_raw_output(
    *,
    repository: EvidenceRepository,
    record: TrialRecord,
    repo_root: Path,
    object_root: Path,
) -> ArtifactReference:
    """Preserve the completed proposal output referenced by Harbor."""
    if record.outputs.raw_output_path is None:
        raise ProposalTrialImportError(
            "completed proposal import has no raw output artifact",
        )
    raw_path = Path(record.outputs.raw_output_path)
    source = raw_path if raw_path.is_absolute() else repo_root / raw_path
    return snapshot_file(
        repository=repository,
        reference=physical_reference(
            kind="proposal-final-output",
            path=source,
            media_type="text/plain",
        ),
        repo_root=repo_root,
        object_root=object_root,
    )


def snapshot_file(
    *,
    repository: EvidenceRepository,
    reference: ArtifactReference,
    repo_root: Path,
    object_root: Path,
) -> ArtifactReference:
    """Copy one hash-checked regular file into its legacy content path."""
    source = Path(reference.path)
    if not source.is_absolute():
        source = repo_root / source
    encoded = read_regular_file(source, label=reference.kind)
    observed_sha256 = hashlib.sha256(encoded).hexdigest()
    if observed_sha256 != reference.sha256:
        raise ProposalTrialImportError(
            f"{reference.kind} changed before host preservation",
        )
    suffix = "".join(source.suffixes) or ".bin"
    filename = f"{safe_segment(reference.kind)}{suffix}"
    path = object_root / observed_sha256 / filename
    with translate_repository_errors(
        label=reference.kind,
        collision_message="content-addressed proposal artifact path contains different bytes",
    ):
        stored = repository.publish_bytes(
            repository.relative_path(path),
            encoded,
        )
    return ArtifactReference(
        kind=reference.kind,
        path=str(stored.path),
        sha256=observed_sha256,
        media_type=reference.media_type,
    )


def persist_model_artifact(
    *,
    repository: EvidenceRepository,
    model: FrozenStrictModel,
    kind: str,
    filename: str,
    object_root: Path,
) -> ArtifactReference:
    """Publish a canonical model and return its immutable reference."""
    path = persist_model_path(
        repository=repository,
        model=model,
        filename=filename,
        object_root=object_root,
    )
    return repository_reference(
        repository=repository,
        kind=kind,
        path=path,
        media_type="application/json",
    )


def persist_model_path(
    *,
    repository: EvidenceRepository,
    model: FrozenStrictModel,
    filename: str,
    object_root: Path,
) -> Path:
    """Publish canonical model bytes at the historical physical-hash path."""
    encoded = canonical_model_bytes(model)
    physical_sha256 = hashlib.sha256(encoded).hexdigest()
    path = object_root / physical_sha256 / filename
    with translate_repository_errors(
        label=filename,
        collision_message="content-addressed proposal artifact path contains different bytes",
    ):
        stored = repository.publish_canonical_model(
            repository.relative_path(path),
            model,
            TypeAdapter(type(model)),
        )
    if stored.artifact.sha256 != physical_sha256:
        raise ProposalTrialImportError(
            "canonical proposal artifact digest differs from its legacy physical identity",
        )
    return stored.artifact.path


def physical_reference(
    *,
    kind: str,
    path: Path,
    media_type: str,
) -> ArtifactReference:
    """Describe a physical regular file with its current byte digest."""
    encoded = read_regular_file(path, label=kind)
    return ArtifactReference(
        kind=kind,
        path=str(path.resolve()),
        sha256=hashlib.sha256(encoded).hexdigest(),
        media_type=media_type,
    )


def repository_reference(
    *,
    repository: EvidenceRepository,
    kind: str,
    path: Path,
    media_type: str,
) -> ArtifactReference:
    """Describe one already-persisted EvidenceRepository artifact."""
    with translate_repository_errors(label=kind):
        artifact = repository.reference(
            repository.relative_path(path),
        )
    return ArtifactReference(
        kind=kind,
        path=str(artifact.path),
        sha256=artifact.sha256,
        media_type=media_type,
    )


def write_or_load_exact_trial_record(
    *,
    repository: EvidenceRepository,
    ledger_root: Path,
    record: TrialRecord,
) -> Path:
    """Persist one TrialRecord or prove the existing first-writer bytes are exact."""
    with translate_repository_errors(label="proposal TrialRecord"):
        repository.relative_path(ledger_root)
    try:
        expected = write_trial_record(ledger_root=ledger_root, record=record)
    except DuplicateTrialRecordError:
        expected = ledger_root / record.experiment_id / f"{record.trial_id}.json"
    try:
        observed = read_trial_record(expected, ledger_root=ledger_root)
    except (OSError, ValueError) as error:
        raise ProposalTrialImportError("persisted proposal TrialRecord cannot be resumed") from error
    if (
        observed.model_dump(mode="python") != record.model_dump(mode="python")
        or observed.run_manifest != record.run_manifest
    ):
        raise ProposalTrialImportError(
            "persisted proposal TrialRecord differs from the resumed import",
        )
    return expected


def merge_artifacts(
    *groups: list[ArtifactReference],
) -> list[ArtifactReference]:
    """Return one stable, identity-deduplicated artifact list."""
    by_identity: dict[tuple[str, str, str], ArtifactReference] = {}
    for artifact in (item for group in groups for item in group):
        by_identity[(artifact.kind, artifact.path, artifact.sha256)] = artifact
    return sorted(
        by_identity.values(),
        key=lambda item: (item.kind, item.path, item.sha256),
    )


def load_session_receipt_from_artifact(
    reference: ArtifactReference,
    *,
    repository: EvidenceRepository,
) -> ProposalSessionReceipt:
    """Load a hash-checked preserved proposal session receipt."""
    verify_artifact(
        reference,
        repository=repository,
    )
    try:
        return ProposalSessionReceipt.model_validate_json(
            load_repository_bytes(
                repository=repository,
                path=Path(reference.path),
                label="persisted proposal session receipt",
            ),
        )
    except ValueError as error:
        raise ProposalTrialImportError(
            "persisted proposal session receipt is invalid",
        ) from error


def verify_artifact(
    reference: ArtifactReference,
    *,
    repository: EvidenceRepository,
) -> None:
    """Reject a persisted artifact whose bytes no longer match its reference."""
    encoded = load_repository_bytes(
        repository=repository,
        path=Path(reference.path),
        label=reference.kind,
    )
    if hashlib.sha256(encoded).hexdigest() != reference.sha256:
        raise ProposalTrialImportError(
            f"persisted artifact changed: {reference.kind}",
        )


def prepare_host_artifacts_repository(
    path: Path,
    *,
    forbidden_roots: tuple[Path, ...],
) -> EvidenceRepository:
    """Create a confined immutable repository disjoint from execution inputs."""
    resolved = validate_host_artifacts_root(
        path,
        forbidden_roots=forbidden_roots,
    )
    with translate_repository_errors(label="proposal import artifacts root"):
        return EvidenceRepository(
            resolved,
            disjoint_roots=forbidden_roots,
        )


def open_host_artifacts_repository(
    path: Path,
) -> EvidenceRepository:
    """Open an existing immutable proposal artifact repository."""
    with translate_repository_errors(label="proposal import artifacts root"):
        resolved = validate_evidence_root(
            Path(path),
            must_exist=True,
        )
        return EvidenceRepository(resolved)


def validate_host_artifacts_root(
    path: Path,
    *,
    forbidden_roots: tuple[Path, ...],
) -> Path:
    """Resolve and validate the proposed host-artifact root."""
    with translate_repository_errors(label="proposal import artifacts root"):
        return validate_evidence_root(
            Path(path).absolute(),
            disjoint_roots=forbidden_roots,
        )


def object_root(
    artifacts_root: Path,
    authorization: GovernedProposalDispatchAuthorization,
) -> Path:
    """Return the legacy object root bound to an authorized dispatch."""
    return artifacts_root / "proposal-trial-imports" / authorization.dispatch.content_sha256 / "objects"


def read_regular_file(
    path: Path,
    *,
    label: str,
) -> bytes:
    """Read bytes only from a non-symlink regular file."""
    reject_symlink_components(path, label=label)
    try:
        mode = path.stat(follow_symlinks=False).st_mode
    except OSError as error:
        raise ProposalTrialImportError(
            f"{label} is missing or cannot be inspected",
        ) from error
    if not stat.S_ISREG(mode):
        raise ProposalTrialImportError(
            f"{label} must be a regular file",
        )
    try:
        return path.read_bytes()
    except OSError as error:
        raise ProposalTrialImportError(
            f"{label} cannot be read",
        ) from error


def reject_symlink_components(
    path: Path,
    *,
    label: str,
) -> None:
    """Reject a path whose existing target or parent is a symbolic link."""
    candidate = Path(path)
    for parent in (candidate, *candidate.parents):
        if parent.exists() and parent.is_symlink():
            raise ProposalTrialImportError(
                f"{label} must not pass through a symbolic link",
            )


@contextmanager
def translate_repository_errors(
    *,
    label: str,
    collision_message: str | None = None,
) -> Iterator[None]:
    """Translate repository boundary failures into the stable import error."""
    try:
        yield
    except ImmutableArtifactCollisionError as error:
        message = collision_message or f"{label} contains different immutable bytes"
        raise ProposalTrialImportError(message) from error
    except ImmutableArtifactConfinementError as error:
        raise ProposalTrialImportError(f"{label} is unconfined: {error}") from error
    except ImmutableArtifactIntegrityError as error:
        raise ProposalTrialImportError(f"{label} is invalid: {error}") from error


def load_repository_bytes(
    *,
    repository: EvidenceRepository,
    path: Path,
    label: str,
) -> bytes:
    """Load repository bytes through confinement and integrity checks."""
    with translate_repository_errors(label=label):
        return repository.load_bytes(
            repository.relative_path(path),
        )


def load_repository_model[ModelT: FrozenStrictModel](
    *,
    repository: EvidenceRepository,
    path: Path,
    model_type: type[ModelT],
    label: str,
) -> ModelT:
    """Load and validate one canonical content-addressed model."""
    with translate_repository_errors(label=label):
        return repository.load_stored_canonical_model(
            repository.relative_path(path),
            TypeAdapter(model_type),
        ).model


def canonical_model_bytes(
    model: FrozenStrictModel,
) -> bytes:
    """Encode a content-addressed model with the historical canonical bytes."""
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def canonical_json(payload: object) -> str:
    """Encode a JSON value with the historical canonical separators."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def safe_segment(value: str) -> str:
    """Normalize an import identity for a path segment or reject it."""
    segment = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    if not segment:
        raise ProposalTrialImportError(
            "proposal import identity has no safe path segment",
        )
    return segment
