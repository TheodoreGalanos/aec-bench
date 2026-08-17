# ABOUTME: Validates the versioned DeepSeek provider and feature qualification matrix.
# ABOUTME: Keeps keyless protocol proof separate from credentialed live-provider claims.

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

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


class DeepSeekQualificationCell(LenientModel):
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


class DeepSeekQualificationRow(LenientModel):
    provider_route: Literal["azure", "deepseek-official"]
    sdk_version: NonEmptyStr
    runtime_version: NonEmptyStr
    status: Literal["partial", "qualified", "unqualified"]
    features: dict[DeepSeekQualificationFeature, DeepSeekQualificationCell]

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


class DeepSeekQualificationMatrix(LenientModel):
    schema_id: Literal["aec-bench/deepseek-qualification/1"] = Field(
        alias="schema",
        serialization_alias="schema",
    )
    matrix_id: NonEmptyStr
    qualification_date: date
    aec_bench_version: NonEmptyStr
    aec_bench_revision: NonEmptyStr
    rows: tuple[DeepSeekQualificationRow, ...]

    @model_validator(mode="after")
    def validate_routes(self) -> Self:
        routes = [row.provider_route for row in self.rows]
        if len(routes) != len(set(routes)):
            raise ValueError("qualification matrix provider routes must be unique")
        if set(routes) != {"azure", "deepseek-official"}:
            raise ValueError("qualification matrix must contain Azure and DeepSeek official routes")
        return self

    def row_for(self, provider_route: str) -> DeepSeekQualificationRow:
        for row in self.rows:
            if row.provider_route == provider_route:
                return row
        raise ValueError(f"qualification matrix does not contain provider route: {provider_route}")


def deepseek_qualification_matrix_path() -> Path:
    """Return the package-owned compatibility and feature matrix."""
    return Path(__file__).parent / "profiles" / "qualification-matrix.json"


def load_deepseek_qualification_matrix(path: Path | None = None) -> DeepSeekQualificationMatrix:
    """Validate and return the current package-owned qualification matrix."""
    source = deepseek_qualification_matrix_path() if path is None else path
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"DeepSeek qualification matrix must be a regular file: {source}")
    return DeepSeekQualificationMatrix.model_validate_json(source.read_text(encoding="utf-8"))
