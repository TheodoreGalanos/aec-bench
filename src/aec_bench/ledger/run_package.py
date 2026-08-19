# ABOUTME: Publishes, exports, imports, and validates one portable run-package archive.
# ABOUTME: Stores the archive once and verifies every referenced artifact before import.

from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import uuid
from collections.abc import Iterator, Mapping
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

import zstandard
from pydantic import BaseModel

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.run_bundle import PublishedRunPackage
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.artifact_repository import ArtifactRepository, canonical_model_bytes
from aec_bench.ledger.durability import fsync_directory, mkdir_durable

RUN_PACKAGE_MEDIA_TYPE = "application/vnd.aec-bench.run-package+tar+zstd"
_MANIFEST_PATH = "run-package.json"
_ARTIFACT_PREFIX = "artifacts/"
_MAX_DECOMPRESSED_BYTES = 4_294_967_296


class RunPackageIntegrityError(ValueError):
    """Raised when run-package bytes do not match their declared references."""


def publish_run_package(*, ledger_root: Path, package: PublishedRunPackage) -> ArtifactRef:
    """Publish one complete run package and record its single archive reference."""

    repository = ArtifactRepository(Path(ledger_root) / "_artifacts")
    archive = build_run_package_archive(package=package, artifact_repository=repository)
    reference = repository.publish_bytes(data=archive, media_type=RUN_PACKAGE_MEDIA_TYPE)
    _write_package_reference(ledger_root=Path(ledger_root), run_id=package.run_plan.run_manifest.run_id, ref=reference)
    return reference


def build_run_package_archive(*, package: PublishedRunPackage, artifact_repository: ArtifactRepository) -> bytes:
    """Build deterministic archive bytes after all referenced artifacts resolve."""

    artifacts = _resolve_package_artifacts(package=package, artifact_repository=artifact_repository)
    members = {_MANIFEST_PATH: canonical_model_bytes(package)}
    members.update({f"{_ARTIFACT_PREFIX}{digest}": payload for digest, payload in artifacts.items()})
    return _build_archive(members)


def read_run_package_archive(data: bytes) -> tuple[PublishedRunPackage, Mapping[str, bytes]]:
    """Validate untrusted archive bytes and return its package and artifact payloads."""

    members = _read_archive(data)
    manifest_bytes = members.get(_MANIFEST_PATH)
    if manifest_bytes is None:
        raise RunPackageIntegrityError(f"run package is missing {_MANIFEST_PATH}")
    try:
        package = PublishedRunPackage.model_validate_json(manifest_bytes)
    except ValueError as error:
        raise RunPackageIntegrityError(f"invalid run-package manifest: {error}") from error
    if canonical_model_bytes(package) != manifest_bytes:
        raise RunPackageIntegrityError("run-package manifest is not canonical JSON")

    artifacts = {
        name.removeprefix(_ARTIFACT_PREFIX): payload
        for name, payload in members.items()
        if name.startswith(_ARTIFACT_PREFIX)
    }
    unexpected_members = sorted(
        name for name in members if name != _MANIFEST_PATH and not name.startswith(_ARTIFACT_PREFIX)
    )
    if unexpected_members:
        raise RunPackageIntegrityError("run package contains unexpected members: " + ", ".join(unexpected_members))

    references = _package_references_from_bytes(package=package, artifacts=artifacts)
    expected_digests = {reference.sha256 for reference in references}
    actual_digests = set(artifacts)
    missing = sorted(expected_digests - actual_digests)
    unexpected = sorted(actual_digests - expected_digests)
    if missing:
        raise RunPackageIntegrityError("run package is missing artifacts: " + ", ".join(missing))
    if unexpected:
        raise RunPackageIntegrityError("run package contains unreferenced artifacts: " + ", ".join(unexpected))
    for reference in references:
        _verify_artifact_bytes(reference, artifacts[reference.sha256])
    return package, MappingProxyType(artifacts)


def import_run_package(*, ledger_root: Path, data: bytes) -> tuple[PublishedRunPackage, ArtifactRef]:
    """Verify one package fully, then publish its artifacts and archive into an empty or compatible ledger."""

    package, artifacts = read_run_package_archive(data)
    repository = ArtifactRepository(Path(ledger_root) / "_artifacts")
    references = _package_references_from_bytes(package=package, artifacts=artifacts)
    for reference in references:
        published = repository.publish_bytes(data=artifacts[reference.sha256], media_type=reference.media_type)
        if published != reference:
            raise RunPackageIntegrityError(f"imported artifact reference changed: {reference.artifact_id}")
    package_ref = repository.publish_bytes(data=data, media_type=RUN_PACKAGE_MEDIA_TYPE)
    _write_package_reference(
        ledger_root=Path(ledger_root),
        run_id=package.run_plan.run_manifest.run_id,
        ref=package_ref,
    )
    return package, package_ref


def export_run_package(*, ledger_root: Path, run_id: str, output: Path) -> ArtifactRef:
    """Write the exact retained archive for one run ID to an explicit output path."""

    reference = read_run_package_reference(ledger_root=ledger_root, run_id=run_id)
    repository = ArtifactRepository(Path(ledger_root) / "_artifacts")
    data = repository.read_bytes(reference)
    read_run_package_archive(data)
    destination = Path(output)
    if destination.exists():
        if not destination.is_file() or destination.read_bytes() != data:
            raise FileExistsError(f"run-package output already exists with different bytes: {destination}")
        return reference
    mkdir_durable(destination.parent)
    temporary = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    try:
        _write_bytes(temporary, data)
        os.link(temporary, destination)
        fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return reference


def read_run_package_reference(*, ledger_root: Path, run_id: str) -> ArtifactRef:
    """Resolve one run domain ID to its retained package artifact."""

    path = _package_reference_path(ledger_root=Path(ledger_root), run_id=run_id)
    if not path.is_file():
        raise FileNotFoundError(f"no published run package exists for run {run_id!r}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        recorded_run_id = payload.pop("run_id")
        reference = ArtifactRef.model_validate(payload)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RunPackageIntegrityError(f"invalid run-package reference at {path}: {error}") from error
    if recorded_run_id != run_id:
        raise RunPackageIntegrityError("run-package reference does not match its run ID locator")
    if reference.media_type != RUN_PACKAGE_MEDIA_TYPE:
        raise RunPackageIntegrityError("run-package reference has the wrong media type")
    return reference


def _resolve_package_artifacts(
    *,
    package: PublishedRunPackage,
    artifact_repository: ArtifactRepository,
) -> dict[str, bytes]:
    references = list(_artifact_references(package))
    payloads: dict[str, bytes] = {}
    for reference in references:
        payloads.setdefault(reference.sha256, artifact_repository.read_bytes(reference))
    trial_records = _trial_records(package=package, artifacts=payloads)
    for record in trial_records:
        for reference in _artifact_references(record):
            payloads.setdefault(reference.sha256, artifact_repository.read_bytes(reference))
            references.append(reference)
    for reference in references:
        _verify_artifact_bytes(reference, payloads[reference.sha256])
    return dict(sorted(payloads.items()))


def _package_references_from_bytes(
    *,
    package: PublishedRunPackage,
    artifacts: Mapping[str, bytes],
) -> tuple[ArtifactRef, ...]:
    references = list(_artifact_references(package))
    for record in _trial_records(package=package, artifacts=artifacts):
        references.extend(_artifact_references(record))
    return tuple(
        sorted(
            references,
            key=lambda reference: (
                reference.sha256,
                reference.artifact_id,
                reference.media_type,
                reference.size_bytes,
            ),
        )
    )


def _trial_records(*, package: PublishedRunPackage, artifacts: Mapping[str, bytes]) -> tuple[TrialRecord, ...]:
    records: list[TrialRecord] = []
    trial_ids: set[str] = set()
    for reference in package.trial_refs:
        payload = artifacts.get(reference.sha256)
        if payload is None:
            raise RunPackageIntegrityError(f"run package is missing trial record {reference.artifact_id}")
        _verify_artifact_bytes(reference, payload)
        try:
            record = TrialRecord.model_validate_json(payload)
        except ValueError as error:
            raise RunPackageIntegrityError(f"invalid trial record {reference.artifact_id}: {error}") from error
        if record.run_id != package.run_plan.run_manifest.run_id:
            raise RunPackageIntegrityError(f"trial {record.trial_id!r} belongs to a different run")
        try:
            record.bind_run_manifest(package.run_plan.run_manifest)
        except ValueError as error:
            raise RunPackageIntegrityError(
                f"trial {record.trial_id!r} does not satisfy its run manifest: {error}"
            ) from error
        if record.trial_id in trial_ids:
            raise RunPackageIntegrityError(f"run package contains duplicate trial id {record.trial_id!r}")
        trial_ids.add(record.trial_id)
        records.append(record)
    return tuple(records)


def _artifact_references(value: Any) -> Iterator[ArtifactRef]:
    if isinstance(value, ArtifactRef):
        yield value
        return
    if isinstance(value, BaseModel):
        for field_name in type(value).model_fields:
            yield from _artifact_references(getattr(value, field_name))
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _artifact_references(item)
        return
    if isinstance(value, list | tuple | set | frozenset):
        for item in value:
            yield from _artifact_references(item)


def _verify_artifact_bytes(reference: ArtifactRef, payload: bytes) -> None:
    if len(payload) != reference.size_bytes:
        raise RunPackageIntegrityError(f"artifact size mismatch: {reference.artifact_id}")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != reference.sha256:
        raise RunPackageIntegrityError(f"artifact SHA-256 mismatch: {reference.artifact_id}")
    expected_id = f"artifacts/sha256/{digest[:2]}/{digest}"
    if reference.artifact_id != expected_id:
        raise RunPackageIntegrityError(f"artifact ID is not canonical: {reference.artifact_id}")


def _build_archive(members: Mapping[str, bytes]) -> bytes:
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(members):
            payload = members[name]
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            info.mode = 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(payload))
    return zstandard.ZstdCompressor(level=10, write_checksum=True, write_content_size=True).compress(
        tar_buffer.getvalue()
    )


def _read_archive(data: bytes) -> Mapping[str, bytes]:
    if not data:
        raise RunPackageIntegrityError("run-package archive must not be empty")
    try:
        tar_bytes = zstandard.ZstdDecompressor().decompress(data, max_output_size=_MAX_DECOMPRESSED_BYTES)
    except zstandard.ZstdError as error:
        raise RunPackageIntegrityError(f"invalid run-package compression: {error}") from error
    members: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
            for member in archive.getmembers():
                name = _portable_member_path(member.name)
                if name in members:
                    raise RunPackageIntegrityError(f"duplicate run-package path: {name}")
                if not member.isfile():
                    raise RunPackageIntegrityError(f"run packages may contain regular files only: {name}")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise RunPackageIntegrityError(f"cannot read run-package member: {name}")
                payload = extracted.read()
                if len(payload) != member.size:
                    raise RunPackageIntegrityError(f"run-package member size mismatch: {name}")
                members[name] = payload
    except tarfile.TarError as error:
        raise RunPackageIntegrityError(f"invalid run-package archive: {error}") from error
    return MappingProxyType(members)


def _portable_member_path(value: str) -> str:
    if "\\" in value:
        raise RunPackageIntegrityError(f"run-package member is not a portable relative path: {value}")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise RunPackageIntegrityError(f"run-package member is not a portable relative path: {value}")
    if path.as_posix() != value:
        raise RunPackageIntegrityError(f"run-package member is not a normalized portable path: {value}")
    if value.startswith(_ARTIFACT_PREFIX):
        digest = value.removeprefix(_ARTIFACT_PREFIX)
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise RunPackageIntegrityError(f"run-package artifact path has an invalid SHA-256: {value}")
    return value


def _write_package_reference(*, ledger_root: Path, run_id: str, ref: ArtifactRef) -> None:
    path = _package_reference_path(ledger_root=ledger_root, run_id=run_id)
    payload = (
        json.dumps(
            {"run_id": run_id, **ref.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    )
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise RunPackageIntegrityError(f"run {run_id!r} already identifies a different published package")
        return
    mkdir_durable(path.parent)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        _write_bytes(temporary, payload.encode("utf-8"))
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            if path.read_text(encoding="utf-8") != payload:
                raise RunPackageIntegrityError(
                    f"run {run_id!r} already identifies a different published package"
                ) from error
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _package_reference_path(*, ledger_root: Path, run_id: str) -> Path:
    locator = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    return Path(ledger_root) / "_run_packages" / f"{locator}.json"


def _write_bytes(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


__all__ = (
    "RUN_PACKAGE_MEDIA_TYPE",
    "RunPackageIntegrityError",
    "build_run_package_archive",
    "export_run_package",
    "import_run_package",
    "publish_run_package",
    "read_run_package_archive",
    "read_run_package_reference",
)
