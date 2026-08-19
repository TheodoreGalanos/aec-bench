# ABOUTME: Validates current and retained DeepSeek provider qualification matrices.
# ABOUTME: Normalizes exact version cells while keeping keyless and live claims separate.

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.provider_provenance import (
    ProviderAdapterIdentity,
    ProviderQualificationCell,
    QualificationEvidenceLevel,
    QualificationStatus,
    ResolvedRuntimeIdentity,
)
from aec_bench.contracts.validators import LenientModel, NonEmptyStr

DeepSeekQualificationFeature = Literal[
    "keyless_protocol",
    "live_basic",
    "live_tool_call",
    "live_output_commit",
    "live_world_episode",
    "max_token_terminal",
    "timeout_cleanup",
    "evidence_redaction",
]
DEEPSEEK_QUALIFICATION_FEATURES = (
    "keyless_protocol",
    "live_basic",
    "live_tool_call",
    "live_output_commit",
    "live_world_episode",
    "max_token_terminal",
    "timeout_cleanup",
    "evidence_redaction",
)
DeepSeekProviderRoute = Literal["azure", "deepseek-official"]


class LegacyDeepSeekQualificationCell(LenientModel):
    status: Literal["passed", "not-run", "not-applicable"]
    evidence: tuple[NonEmptyStr, ...] = ()
    reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status == "passed" and (not self.evidence or self.reason is not None):
            raise ValueError("a passed qualification cell requires evidence and cannot have a reason")
        if self.status != "passed" and (self.evidence or self.reason is None):
            raise ValueError("an unpassed qualification cell requires a reason and cannot claim evidence")
        return self


class LegacyDeepSeekQualificationRow(LenientModel):
    provider_route: DeepSeekProviderRoute
    sdk_version: NonEmptyStr
    runtime_version: NonEmptyStr
    status: Literal["partial", "qualified", "unqualified"]
    features: dict[DeepSeekQualificationFeature, LegacyDeepSeekQualificationCell]

    @model_validator(mode="after")
    def validate_row(self) -> Self:
        expected = set(DEEPSEEK_QUALIFICATION_FEATURES)
        if set(self.features) != expected:
            raise ValueError("qualification row must contain every supported feature")
        all_passed = all(cell.status == "passed" for cell in self.features.values())
        if (self.status == "qualified") != all_passed:
            raise ValueError("qualified provider status requires every feature to pass")
        return self

    @property
    def passed_features(self) -> tuple[str, ...]:
        return tuple(sorted(name for name, cell in self.features.items() if cell.status == "passed"))


class LegacyDeepSeekQualificationMatrix(LenientModel):
    schema_id: Literal["aec-bench/deepseek-qualification/1"] = Field(
        alias="schema",
        serialization_alias="schema",
    )
    matrix_id: NonEmptyStr
    qualification_date: date
    aec_bench_version: NonEmptyStr
    aec_bench_revision: NonEmptyStr
    rows: tuple[LegacyDeepSeekQualificationRow, ...]

    @model_validator(mode="after")
    def validate_routes(self) -> Self:
        _validate_routes(tuple(row.provider_route for row in self.rows))
        return self

    def row_for(self, provider_route: str) -> LegacyDeepSeekQualificationRow:
        for row in self.rows:
            if row.provider_route == provider_route:
                return row
        raise ValueError(f"qualification matrix does not contain provider route: {provider_route}")


class DeepSeekQualificationCell(LenientModel):
    provider_route: DeepSeekProviderRoute
    feature: DeepSeekQualificationFeature
    adapter_identity: ProviderAdapterIdentity
    sdk: ResolvedRuntimeIdentity
    runtime: ResolvedRuntimeIdentity
    evidence_level: QualificationEvidenceLevel
    status: QualificationStatus
    evidence: tuple[ArtifactRef, ...] = ()
    qualified_at: datetime | None = None
    reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        self.normalized()
        if self.feature.startswith("live_") != (self.evidence_level == "live"):
            raise ValueError(
                "live qualification features require live evidence and other features require keyless evidence"
            )
        return self

    def normalized(self) -> ProviderQualificationCell:
        return ProviderQualificationCell(
            provider_route=self.provider_route,
            feature=self.feature,
            adapter_identity=self.adapter_identity,
            sdk=self.sdk,
            runtime=self.runtime,
            evidence_level=self.evidence_level,
            status=self.status,
            evidence=self.evidence,
            qualified_at=self.qualified_at,
            reason=self.reason,
        )


class DeepSeekQualificationMatrix(LenientModel):
    schema_id: Literal["aec-bench/deepseek-qualification/2"] = Field(
        alias="schema",
        serialization_alias="schema",
    )
    matrix_id: NonEmptyStr
    cells: tuple[DeepSeekQualificationCell, ...]

    @model_validator(mode="after")
    def validate_cells(self) -> Self:
        keys = [(cell.provider_route, cell.feature) for cell in self.cells]
        if len(keys) != len(set(keys)):
            raise ValueError("qualification matrix cells must have unique provider route and feature identities")
        _validate_routes(tuple(cell.provider_route for cell in self.cells))
        for route in ("azure", "deepseek-official"):
            features = {cell.feature for cell in self.cells if cell.provider_route == route}
            if features != set(DEEPSEEK_QUALIFICATION_FEATURES):
                raise ValueError("each qualification route must contain every supported feature")
        return self

    def cells_for(self, provider_route: str) -> tuple[DeepSeekQualificationCell, ...]:
        selected = tuple(cell for cell in self.cells if cell.provider_route == provider_route)
        if not selected:
            raise ValueError(f"qualification matrix does not contain provider route: {provider_route}")
        return selected


DeepSeekQualificationMatrixDocument = DeepSeekQualificationMatrix | LegacyDeepSeekQualificationMatrix


class DeepSeekRuntimeQualification:
    """Normalized route result for one exact runtime version set."""

    def __init__(self, *, status: QualificationStatus, qualified_features: tuple[str, ...]) -> None:
        self.status = status
        self.qualified_features = qualified_features


def deepseek_qualification_matrix_path() -> Path:
    """Return the package-owned compatibility and feature matrix."""
    return Path(__file__).parent / "profiles" / "qualification-matrix.json"


def load_deepseek_qualification_matrix(path: Path | None = None) -> DeepSeekQualificationMatrixDocument:
    """Validate current v2 matrices and keep the independently versioned v1 reader."""
    source = deepseek_qualification_matrix_path() if path is None else Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"DeepSeek qualification matrix must be a regular file: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"DeepSeek qualification matrix must contain JSON: {source}") from exc
    if not isinstance(payload, dict):
        raise ValueError("DeepSeek qualification matrix must contain an object")
    schema = payload.get("schema")
    if schema == "aec-bench/deepseek-qualification/1":
        return LegacyDeepSeekQualificationMatrix.model_validate(payload)
    if schema != "aec-bench/deepseek-qualification/2":
        raise ValueError(f"unsupported DeepSeek qualification matrix schema: {schema!r}")
    matrix = DeepSeekQualificationMatrix.model_validate(payload)
    _verify_evidence_references(matrix, source.parent)
    return matrix


def qualification_for_runtime(
    matrix: DeepSeekQualificationMatrixDocument,
    *,
    provider_route: str,
    adapter_identity: ProviderAdapterIdentity,
    sdk: ResolvedRuntimeIdentity,
    runtime: ResolvedRuntimeIdentity,
) -> DeepSeekRuntimeQualification:
    """Return honest qualification only for the matrix's exact version set."""
    if isinstance(matrix, LegacyDeepSeekQualificationMatrix):
        row = matrix.row_for(provider_route)
        revision_matches = adapter_identity.source_revision == matrix.aec_bench_revision
        versions_match = (
            adapter_identity.package_version == matrix.aec_bench_version
            and sdk.distribution_version == row.sdk_version
            and runtime.distribution_version == row.runtime_version
        )
        return DeepSeekRuntimeQualification(
            status=row.status if revision_matches and versions_match else "unqualified",
            qualified_features=row.passed_features if revision_matches and versions_match else (),
        )
    cells = matrix.cells_for(provider_route)
    versions_match = all(
        cell.adapter_identity == adapter_identity and cell.sdk == sdk and cell.runtime == runtime for cell in cells
    )
    if not versions_match:
        return DeepSeekRuntimeQualification(status="unqualified", qualified_features=())
    qualified_features = tuple(sorted(cell.feature for cell in cells if cell.status == "qualified"))
    if all(cell.status == "qualified" for cell in cells):
        status: QualificationStatus = "qualified"
    elif any(cell.status in {"partial", "qualified"} for cell in cells):
        status = "partial"
    else:
        status = "unqualified"
    return DeepSeekRuntimeQualification(status=status, qualified_features=qualified_features)


def _verify_evidence_references(matrix: DeepSeekQualificationMatrix, root: Path) -> None:
    for cell in matrix.cells:
        for reference in cell.evidence:
            relative = PurePosixPath(reference.artifact_id)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("qualification evidence artifact_id must stay relative to the matrix")
            path = root.joinpath(*relative.parts)
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError(f"qualification evidence is unavailable: {reference.artifact_id}")
            content = path.read_bytes()
            if len(content) != reference.size_bytes or hashlib.sha256(content).hexdigest() != reference.sha256:
                raise ValueError(f"qualification evidence does not match its ArtifactRef: {reference.artifact_id}")


def _validate_routes(routes: tuple[str, ...]) -> None:
    if set(routes) != {"azure", "deepseek-official"}:
        raise ValueError("qualification matrix must contain Azure and DeepSeek official routes")


def qualification_matrix_payload(document: DeepSeekQualificationMatrixDocument) -> dict[str, Any]:
    """Return one JSON-ready qualification document while preserving future fields."""
    return document.model_dump(mode="json", by_alias=True)


__all__ = (
    "DEEPSEEK_QUALIFICATION_FEATURES",
    "DeepSeekQualificationCell",
    "DeepSeekQualificationMatrix",
    "DeepSeekQualificationMatrixDocument",
    "DeepSeekRuntimeQualification",
    "LegacyDeepSeekQualificationMatrix",
    "deepseek_qualification_matrix_path",
    "load_deepseek_qualification_matrix",
    "qualification_for_runtime",
    "qualification_matrix_payload",
)
