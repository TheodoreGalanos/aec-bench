# ABOUTME: Persists schema-2 run manifests and append-only trial records in the Python ledger.
# ABOUTME: Materializes typed extensions as exact artifacts before one trial references them.

import hashlib
import os
import uuid
from pathlib import Path

from pydantic import BaseModel

from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind, AuthorityEvidenceRef
from aec_bench.contracts.trial_record import (
    EvidenceStatus,
    FileReference,
    RunManifest,
    TrialArtifactRef,
    TrialExtensionRef,
    TrialInput,
    TrialOutput,
    TrialRecord,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.durability import fsync_directory, mkdir_durable


class DuplicateTrialRecordError(Exception):
    pass


class RunManifestConflictError(Exception):
    pass


def write_trial_record(*, ledger_root: Path, record: TrialRecord) -> Path:
    manifest = record.run_manifest
    path = ledger_root / manifest.experiment_id / f"{record.trial_id}.json"
    return _write_trial_record(
        path=path,
        manifest_path=run_manifest_path(
            ledger_root=ledger_root,
            experiment_id=manifest.experiment_id,
            run_id=manifest.run_id,
        ),
        artifact_root=ledger_root / "_artifacts",
        record=record,
    )


def write_trial_record_at(*, path: Path, record: TrialRecord) -> Path:
    """Write one portable record package while preserving an explicit public path."""

    locator = _run_manifest_locator(record.run_id)
    return _write_trial_record(
        path=path,
        manifest_path=path.parent / "_runs" / f"{locator}.json",
        artifact_root=path.parent / "_artifacts",
        record=record,
    )


def _write_trial_record(
    *,
    path: Path,
    manifest_path: Path,
    artifact_root: Path,
    record: TrialRecord,
) -> Path:
    manifest = record.run_manifest
    _write_run_manifest_path(path=manifest_path, manifest=manifest)
    _materialize_artifacts(artifact_root=artifact_root, record=record)
    _materialize_extensions(artifact_root=artifact_root, record=record)
    _finalize_evidence_status(record)
    record.bind_run_manifest(manifest)
    persisted = TrialRecord.model_validate(record.model_dump(mode="python"))
    mkdir_durable(path.parent)
    temporary = _temporary_path(path.parent)
    try:
        _write_record_temp(temporary, persisted.model_dump_json(indent=2))
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise DuplicateTrialRecordError(f"trial record already exists: {path}") from exc
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def write_trial_records(*, ledger_root: Path, records: list[TrialRecord]) -> list[Path]:
    return [write_trial_record(ledger_root=ledger_root, record=record) for record in records]


def materialize_trial_record(*, artifact_root: Path, record: TrialRecord) -> TrialRecord:
    """Publish pending trial artifacts and return a path-independent record."""

    manifest = record.run_manifest
    _materialize_artifacts(artifact_root=artifact_root, record=record)
    _materialize_extensions(artifact_root=artifact_root, record=record)
    _finalize_evidence_status(record)
    materialized = TrialRecord.model_validate(record.model_dump(mode="python"))
    materialized.bind_run_manifest(manifest)
    materialized.bind_artifact_root(artifact_root)
    return materialized


def write_run_manifest(*, ledger_root: Path, manifest: RunManifest) -> Path:
    path = run_manifest_path(ledger_root=ledger_root, experiment_id=manifest.experiment_id, run_id=manifest.run_id)
    return _write_run_manifest_path(path=path, manifest=manifest)


def _write_run_manifest_path(*, path: Path, manifest: RunManifest) -> Path:
    payload = manifest.model_dump_json(indent=2)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise RunManifestConflictError(f"run manifest identity resolves to different content: {manifest.run_id}")
        return path
    mkdir_durable(path.parent)
    temporary = _temporary_path(path.parent)
    try:
        _write_record_temp(temporary, payload)
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            if path.read_text(encoding="utf-8") != payload:
                raise RunManifestConflictError(
                    f"run manifest identity resolves to different content: {manifest.run_id}"
                ) from error
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def run_manifest_path(*, ledger_root: Path, experiment_id: str, run_id: str) -> Path:
    locator = _run_manifest_locator(run_id)
    return ledger_root / experiment_id / "_runs" / f"{locator}.json"


def _run_manifest_locator(run_id: str) -> str:
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()


def _materialize_extensions(*, artifact_root: Path, record: TrialRecord) -> None:
    pending = record.pending_extensions
    if not pending:
        return
    references = {item.extension_kind: item for item in record.extension_refs}
    repository = ArtifactRepository(artifact_root)
    for kind, value in pending.items():
        if not isinstance(value, BaseModel):
            raise TypeError(f"trial extension must be a Pydantic model: {kind}")
        ref = repository.publish_model(value=value, media_type="application/json")
        existing = references.get(kind)
        if existing is not None and existing.artifact != ref:
            raise ValueError(f"trial extension reference conflicts with attached value: {kind}")
        references[kind] = TrialExtensionRef(extension_kind=kind, artifact=ref)
    record.extension_refs = tuple(references[kind] for kind in sorted(references))


def _materialize_artifacts(*, artifact_root: Path, record: TrialRecord) -> None:
    pending = record.pending_artifacts
    if not pending:
        return
    expected_hashes = record.pending_artifact_hashes
    if set(expected_hashes) != set(pending):
        raise RuntimeError("pending trial artifact hashes do not match pending artifact roles")
    repository = ArtifactRepository(artifact_root)
    output = record.output
    output_artifacts = list(output.artifacts if output is not None else ())
    authority_evidence = list(record.authority_evidence)
    input_files = list(record.input.input_files or ())
    output_updates: dict[str, object] = {}
    for role, (path, media_type, logical_path) in sorted(pending.items()):
        if not path.is_file():
            raise FileNotFoundError(f"trial artifact does not exist for role {role}: {path}")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected_hashes[role]:
            raise ValueError(f"trial artifact changed after attachment: {role}")
        semantic_role = role.removeprefix("output:")
        if role.startswith("output:"):
            semantic_role = semantic_role.rpartition(":")[0] or semantic_role
        if not payload and semantic_role in {"conversation", "trajectory"}:
            continue
        ref = repository.publish_bytes(data=payload, media_type=media_type)
        if role in {"raw_output", "conversation", "trajectory"}:
            output_updates[role] = ref
            output_artifacts.append(TrialArtifactRef(role=role, artifact=ref, logical_path=logical_path))
        elif role == "provider_evidence":
            record.provider_evidence = ref
        elif role.startswith("authority:"):
            _, kind, protocol = role.split(":", 2)
            authority_evidence.append(
                AuthorityEvidenceRef(
                    authority_kind=AuthorityEvidenceKind(kind),
                    protocol=protocol,
                    artifact=ref,
                )
            )
        elif role.startswith("input:"):
            source = role.removeprefix("input:").partition(":")[0]
            input_files.append(FileReference(artifact=ref, source=source or None))
        elif role.startswith("extension-ref:"):
            kind = role.removeprefix("extension-ref:")
            record.extension_refs = (*record.extension_refs, TrialExtensionRef(extension_kind=kind, artifact=ref))
        else:
            output_role = role.removeprefix("output:")
            if role.startswith("output:"):
                output_role = output_role.rpartition(":")[0] or output_role
            output_artifacts.append(TrialArtifactRef(role=output_role, artifact=ref, logical_path=logical_path))
    if output is not None:
        record.output = TrialOutput.model_validate(
            {
                **output.model_dump(mode="python"),
                **output_updates,
                "artifacts": tuple(dict.fromkeys(output_artifacts)),
            }
        )
    if input_files:
        record.input = TrialInput.model_validate(
            {
                **record.input.model_dump(mode="python"),
                "input_files": tuple(input_files),
            }
        )
    record.authority_evidence = tuple(authority_evidence)


def _finalize_evidence_status(record: TrialRecord) -> None:
    if record.evidence_status is not EvidenceStatus.PENDING:
        return
    expected = tuple(item for item in record.run_manifest.expected_authorities if item.required)
    if not expected:
        record.evidence_status = EvidenceStatus.NOT_REQUIRED
        return
    actual = {(item.authority_kind, item.protocol) for item in record.authority_evidence}
    complete = all(
        (record.provider_evidence is not None)
        if item.authority_kind is AuthorityEvidenceKind.PROVIDER
        else (item.authority_kind, item.protocol) in actual
        for item in expected
    )
    record.evidence_status = EvidenceStatus.VERIFIED if complete else EvidenceStatus.INCOMPLETE


def _write_record_temp(path: Path, payload: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _temporary_path(parent: Path) -> Path:
    """Keep atomic-write names bounded independently of the public record name."""

    return parent / f".record.{uuid.uuid4().hex}.tmp"
