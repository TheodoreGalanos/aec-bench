# ABOUTME: Provides internal technical inspection of exact artifacts and provider qualification.
# ABOUTME: Keeps full digests behind explicit read-time integrity routes instead of routine views.

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from aec_bench.adapters.deepseek_harness.qualification import (
    DeepSeekQualificationMatrix,
    deepseek_qualification_matrix_path,
    load_deepseek_qualification_matrix,
)
from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.reader import read_trial_records
from aec_bench.web.dependencies import get_web_settings, require_internal_access
from aec_bench.web.schemas import (
    ArtifactIntegrityResponse,
    ProviderAdapterIdentitySchema,
    ProviderQualificationCellSchema,
    ProviderQualificationResponse,
    QualificationEvidenceSchema,
    RuntimeIdentitySchema,
    TrialEvidenceItemSchema,
    TrialEvidenceResponse,
)

router = APIRouter(dependencies=[Depends(require_internal_access)])


def _verified_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _record_references(record: TrialRecord) -> tuple[ArtifactRef, ...]:
    references = [
        *(item.artifact for item in record.extension_refs),
        *(item.artifact for item in record.authority_evidence),
        *(item.artifact for item in record.input.input_files or ()),
        *((item.artifact for item in record.output.artifacts) if record.output is not None else ()),
    ]
    if record.provider_evidence is not None:
        references.append(record.provider_evidence)
    return tuple(references)


def _all_records(ledger_root: Path) -> list[TrialRecord]:
    records: list[TrialRecord] = []
    if not ledger_root.is_dir():
        return records
    for experiment_dir in sorted(ledger_root.iterdir()):
        if experiment_dir.is_dir() and not experiment_dir.name.startswith("_"):
            records.extend(read_trial_records(ledger_root, experiment_id=experiment_dir.name))
    return records


def _find_ledger_reference(ledger_root: Path, artifact_id: str) -> ArtifactRef:
    for record in _all_records(ledger_root):
        for reference in _record_references(record):
            if reference.artifact_id == artifact_id:
                return reference
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact reference not found")


def _read_ledger_artifact(ledger_root: Path, artifact_id: str) -> tuple[ArtifactRef, bytes]:
    reference = _find_ledger_reference(ledger_root, artifact_id)
    try:
        payload = ArtifactRepository(ledger_root / "_artifacts").read_bytes(reference)
    except (OSError, RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"artifact integrity verification failed: {error}",
        ) from error
    return reference, payload


def _qualification_matrix() -> DeepSeekQualificationMatrix:
    matrix = load_deepseek_qualification_matrix()
    if not isinstance(matrix, DeepSeekQualificationMatrix):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="the retained qualification matrix uses the legacy API vocabulary",
        )
    return matrix


def _find_qualification_reference(artifact_id: str) -> ArtifactRef:
    matrix = _qualification_matrix()
    for cell in matrix.cells:
        references = list(cell.evidence)
        if cell.adapter_identity.source_snapshot is not None:
            references.append(cell.adapter_identity.source_snapshot)
        for reference in references:
            if reference.artifact_id == artifact_id:
                return reference
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="qualification artifact reference not found")


def _read_qualification_artifact(artifact_id: str) -> tuple[ArtifactRef, bytes]:
    reference = _find_qualification_reference(artifact_id)
    relative = PurePosixPath(reference.artifact_id)
    root = deepseek_qualification_matrix_path().parent
    path = root.joinpath(*relative.parts)
    payload = path.read_bytes()
    if len(payload) != reference.size_bytes or hashlib.sha256(payload).hexdigest() != reference.sha256:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="qualification artifact integrity verification failed",
        )
    return reference, payload


def _integrity_response(reference: ArtifactRef) -> ArtifactIntegrityResponse:
    return ArtifactIntegrityResponse(
        artifact_id=reference.artifact_id,
        sha256=reference.sha256,
        size_bytes=reference.size_bytes,
        verified=True,
        verified_at=_verified_at(),
    )


@router.get("/api/artifacts/{artifact_id:path}/integrity")
def artifact_integrity(request: Request, artifact_id: str) -> ArtifactIntegrityResponse:
    """Verify one referenced ledger artifact and return its full digest."""
    settings = get_web_settings(request)
    reference, _payload = _read_ledger_artifact(settings.ledger_root, artifact_id)
    return _integrity_response(reference)


@router.get("/api/artifacts/{artifact_id:path}/content")
def artifact_content(request: Request, artifact_id: str) -> Response:
    """Verify and return the exact bytes for one referenced ledger artifact."""
    settings = get_web_settings(request)
    reference, payload = _read_ledger_artifact(settings.ledger_root, artifact_id)
    return Response(content=payload, media_type=reference.media_type)


@router.get("/api/trials/{experiment_id}/{trial_id}/evidence")
def trial_evidence(request: Request, experiment_id: str, trial_id: str) -> TrialEvidenceResponse:
    """Return authority-owned evidence references for one trial."""
    settings = get_web_settings(request)
    records = read_trial_records(settings.ledger_root, experiment_id=experiment_id)
    record = next((item for item in records if item.trial_id == trial_id), None)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trial not found")

    items = [
        TrialEvidenceItemSchema(
            authority_kind=item.authority_kind.value,
            protocol=item.protocol,
            artifact_id=item.artifact.artifact_id,
            media_type=item.artifact.media_type,
            size_bytes=item.artifact.size_bytes,
            integrity_url=f"/api/artifacts/{item.artifact.artifact_id}/integrity",
            content_url=f"/api/artifacts/{item.artifact.artifact_id}/content",
        )
        for item in record.authority_evidence
    ]
    if record.provider_evidence is not None:
        provider_protocol = next(
            (
                item.protocol
                for item in record.run_manifest.expected_authorities
                if item.authority_kind is AuthorityEvidenceKind.PROVIDER
            ),
            "aec-bench/provider-evidence-manifest/1",
        )
        items.append(
            TrialEvidenceItemSchema(
                authority_kind=AuthorityEvidenceKind.PROVIDER.value,
                protocol=provider_protocol,
                artifact_id=record.provider_evidence.artifact_id,
                media_type=record.provider_evidence.media_type,
                size_bytes=record.provider_evidence.size_bytes,
                integrity_url=f"/api/artifacts/{record.provider_evidence.artifact_id}/integrity",
                content_url=f"/api/artifacts/{record.provider_evidence.artifact_id}/content",
            )
        )
    return TrialEvidenceResponse(
        experiment_id=experiment_id,
        trial_id=trial_id,
        evidence_status=record.evidence_status.value,
        evidence=items,
    )


def _qualification_evidence(reference: ArtifactRef) -> QualificationEvidenceSchema:
    return QualificationEvidenceSchema(
        artifact_id=reference.artifact_id,
        media_type=reference.media_type,
        size_bytes=reference.size_bytes,
        integrity_url=f"/api/provider-qualification/artifacts/{reference.artifact_id}/integrity",
        content_url=f"/api/provider-qualification/artifacts/{reference.artifact_id}/content",
    )


@router.get("/api/provider-qualification/artifacts/{artifact_id:path}/integrity")
def qualification_artifact_integrity(artifact_id: str) -> ArtifactIntegrityResponse:
    """Verify one retained provider qualification artifact and return its full digest."""
    reference, _payload = _read_qualification_artifact(artifact_id)
    return _integrity_response(reference)


@router.get("/api/provider-qualification/artifacts/{artifact_id:path}/content")
def qualification_artifact_content(artifact_id: str) -> Response:
    """Verify and return one retained provider qualification artifact."""
    reference, payload = _read_qualification_artifact(artifact_id)
    return Response(content=payload, media_type=reference.media_type)


@router.get("/api/provider-qualification")
def provider_qualification() -> ProviderQualificationResponse:
    """Return feature claims for each exact provider package and runtime set."""
    matrix = _qualification_matrix()
    cells = []
    for cell in matrix.cells:
        source_snapshot = cell.adapter_identity.source_snapshot
        cells.append(
            ProviderQualificationCellSchema(
                provider_route=cell.provider_route,
                feature=cell.feature,
                adapter_identity=ProviderAdapterIdentitySchema(
                    adapter_id=cell.adapter_identity.adapter_id,
                    package_version=cell.adapter_identity.package_version,
                    source_revision=cell.adapter_identity.source_revision,
                    source_snapshot=(_qualification_evidence(source_snapshot) if source_snapshot is not None else None),
                ),
                sdk=RuntimeIdentitySchema(**cell.sdk.model_dump()),
                runtime=RuntimeIdentitySchema(**cell.runtime.model_dump()),
                evidence_level=cell.evidence_level,
                qualification_status=cell.status,
                qualified_at=cell.qualified_at.isoformat() if cell.qualified_at is not None else None,
                reason=cell.reason,
                evidence=[_qualification_evidence(reference) for reference in cell.evidence],
            )
        )
    return ProviderQualificationResponse(matrix_id=matrix.matrix_id, cells=cells)
