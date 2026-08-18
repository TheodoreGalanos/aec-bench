# ABOUTME: Contract models for task genome decomposition and snapshot-bound review artifacts.
# ABOUTME: Keeps derived review evidence separate from runnable task identity and source bytes.

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.validators import (
    FrozenStrictModel,
    NonEmptyStr,
    StrictModel,
    ensure_optional_relative_path,
    ensure_relative_path,
)

Confidence = Literal["high", "medium", "low"]
TaskGenomeStatus = Literal["extracted", "needs_review", "reviewed"]
TASK_GENOME_REVIEW_MEDIA_TYPE = "application/vnd.aec-bench.task-genome-review+json"


class SourceSpan(FrozenStrictModel):
    """One source location resolved only through the review's task snapshot."""

    path: NonEmptyStr
    start_line: PositiveInt | None = None
    end_line: PositiveInt | None = None
    section: str | None = None
    signal: str | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return ensure_relative_path(value)

    @field_validator("section", "signal")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("source span text must not be blank")
        return value

    @model_validator(mode="after")
    def validate_line_range(self) -> Self:
        if (self.start_line is None) != (self.end_line is None):
            raise ValueError("source span must set both start_line and end_line")
        if self.start_line is not None and self.end_line is not None and self.end_line < self.start_line:
            raise ValueError("source span end_line must not precede start_line")
        return self


class DomainFrame(StrictModel):
    discipline: NonEmptyStr
    subdomain: NonEmptyStr
    role: str | None = None
    standards: list[str] = Field(default_factory=list)


class Scenario(StrictModel):
    summary: NonEmptyStr
    setting: str | None = None


class InputBundle(StrictModel):
    quantities: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("artifacts")
    @classmethod
    def validate_artifacts(cls, value: list[str]) -> list[str]:
        return [ensure_relative_path(item) for item in value]


class PressurePoint(StrictModel):
    id: NonEmptyStr
    type: NonEmptyStr
    description: NonEmptyStr
    confidence: Confidence = "medium"


class OutputContract(StrictModel):
    format: NonEmptyStr
    required_fields: list[str] = Field(default_factory=list)
    output_path: str | None = None


class VerifierContract(StrictModel):
    mode: NonEmptyStr
    script: str | None = None
    field_scores: dict[str, str] = Field(default_factory=dict)
    validation_rules: dict[str, int] = Field(default_factory=dict)

    @field_validator("script")
    @classmethod
    def validate_script(cls, value: str | None) -> str | None:
        return ensure_optional_relative_path(value)


class ExtractionSummary(StrictModel):
    deterministic_fields: list[str] = Field(default_factory=list)
    reasoning_review_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TaskGenomeManifest(StrictModel):
    """Derived semantic decomposition without a source locator or review state."""

    task_id: NonEmptyStr
    domain_frame: DomainFrame
    scenario: Scenario
    input_bundle: InputBundle
    reasoning_moves: list[str] = Field(default_factory=list)
    pressure_points: list[PressurePoint] = Field(default_factory=list)
    output_contract: OutputContract
    verifier_contract: VerifierContract
    difficulty_controls: dict[str, Any] = Field(default_factory=dict)
    trajectory_affordances: dict[str, Any] = Field(default_factory=dict)
    extraction: ExtractionSummary


class TaskGenomeReview(FrozenStrictModel):
    """Regenerable review evidence bound to one exact runnable task snapshot."""

    task: TaskSnapshotRef
    status: TaskGenomeStatus
    extractor: NonEmptyStr
    reviewer: NonEmptyStr | None = None
    genome: TaskGenomeManifest
    evidence: dict[NonEmptyStr, list[SourceSpan]]

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, value: dict[str, list[SourceSpan]]) -> dict[str, list[SourceSpan]]:
        if not value:
            raise ValueError("task genome review evidence must not be empty")
        empty_keys = [key for key, spans in value.items() if not spans]
        if empty_keys:
            raise ValueError(f"task genome evidence entries must contain source spans: {', '.join(empty_keys)}")
        return value

    @model_validator(mode="after")
    def validate_review(self) -> Self:
        if self.task.task_id != self.genome.task_id:
            raise ValueError("task genome review task does not match the genome task_id")
        if self.status == "reviewed" and self.reviewer is None:
            raise ValueError("reviewed task genome evidence must identify its reviewer")
        return self

    def is_stale(self, current_task: TaskSnapshotRef) -> bool:
        """Return whether the selected task snapshot differs from this review."""

        return self.task != current_task


__all__ = (
    "TASK_GENOME_REVIEW_MEDIA_TYPE",
    "Confidence",
    "DomainFrame",
    "ExtractionSummary",
    "InputBundle",
    "OutputContract",
    "PressurePoint",
    "Scenario",
    "SourceSpan",
    "TaskGenomeManifest",
    "TaskGenomeReview",
    "TaskGenomeStatus",
    "VerifierContract",
)
