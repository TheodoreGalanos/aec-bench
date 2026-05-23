# ABOUTME: Pydantic models for structured reviewer workflow records in the feedback domain.
# ABOUTME: Defines append-only annotations, adjudication, calibration,
# ABOUTME: assignments, and derived items.

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.evaluation_result import Annotation, ConfidenceMetadata, Judgment
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.validators import StrictModel, ensure_non_empty_string


class CalibrationStatus(StrEnum):
    UNCALIBRATED = "uncalibrated"
    PROVISIONAL = "provisional"
    CALIBRATED = "calibrated"


class AdjudicationStatus(StrEnum):
    AGREED = "agreed"
    NEEDS_ADJUDICATION = "needs_adjudication"
    ADJUDICATED = "adjudicated"
    CONTESTED = "contested"


class FeedbackItemType(StrEnum):
    VERIFIER_FIX = "verifier_fix"
    INSTRUCTION_REVISION = "instruction_revision"
    INSTANCE_PROPOSAL = "instance_proposal"
    RUBRIC_UPDATE = "rubric_update"
    LIFECYCLE_CHANGE = "lifecycle_change"


class FeedbackItemStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class ReviewerWeighting(StrictModel):
    calibration_score: float
    discipline_score: float
    experience_score: float

    @field_validator("calibration_score", "discipline_score", "experience_score")
    @classmethod
    def validate_score(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "weighting scores must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value


class ReviewerProfile(StrictModel):
    reviewer_id: str
    discipline: str
    calibration_status: CalibrationStatus
    calibration_version: str | None = None
    can_review_holdout: bool = False
    weighting: ReviewerWeighting
    created_at: datetime
    updated_at: datetime

    @field_validator("reviewer_id", "discipline")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class ReviewAssignment(StrictModel):
    assignment_id: str
    trial_id: str
    experiment_id: str
    task_id: str
    task_visibility: Visibility
    reviewer_id: str
    reviewer_discipline: str
    assigned_at: datetime
    is_calibration: bool = False
    assignment_reason: str

    @field_validator(
        "assignment_id",
        "trial_id",
        "experiment_id",
        "task_id",
        "reviewer_id",
        "reviewer_discipline",
        "assignment_reason",
    )
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)


class FeedbackAnnotation(StrictModel):
    annotation_id: str
    trial_id: str
    experiment_id: str
    task_id: str
    task_visibility: Visibility
    reviewer_id: str
    reviewer_discipline: str
    judgment: Judgment
    categories: list[str] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime
    is_calibration: bool = False
    calibration_version: str | None = None

    @field_validator(
        "annotation_id",
        "trial_id",
        "experiment_id",
        "task_id",
        "reviewer_id",
        "reviewer_discipline",
    )
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, value: list[str]) -> list[str]:
        return [ensure_non_empty_string(category) for category in value]

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return ensure_non_empty_string(value)

    @field_validator("calibration_version")
    @classmethod
    def validate_calibration_version(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return ensure_non_empty_string(value)

    @model_validator(mode="after")
    def validate_calibration_fields(self) -> FeedbackAnnotation:
        if self.is_calibration and self.calibration_version is None:
            msg = "calibration annotations must include calibration_version"
            raise ValueError(msg)
        if not self.is_calibration and self.calibration_version is not None:
            msg = "non-calibration annotations must not include calibration_version"
            raise ValueError(msg)
        return self


class CalibrationReference(StrictModel):
    trial_id: str
    reference_judgment: Judgment
    reference_categories: list[str] = Field(default_factory=list)
    calibration_version: str

    @field_validator("trial_id", "calibration_version")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)

    @field_validator("reference_categories")
    @classmethod
    def validate_categories(cls, value: list[str]) -> list[str]:
        return [ensure_non_empty_string(category) for category in value]


class ReviewerCalibrationResult(StrictModel):
    reviewer_id: str
    reviewer_discipline: str
    calibration_version: str
    total_cases: int
    agreement_rate: float
    passed: bool
    scored_at: datetime

    @field_validator("reviewer_id", "reviewer_discipline", "calibration_version")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)

    @field_validator("total_cases")
    @classmethod
    def validate_total_cases(cls, value: int) -> int:
        if value < 0:
            msg = "total_cases must be non-negative"
            raise ValueError(msg)
        return value

    @field_validator("agreement_rate")
    @classmethod
    def validate_agreement_rate(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "agreement_rate must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value


class AdjudicationRecord(StrictModel):
    decision_id: str
    trial_id: str
    experiment_id: str
    task_id: str
    task_visibility: Visibility
    status: AdjudicationStatus
    final_judgment: Judgment | None = None
    categories: list[str] = Field(default_factory=list)
    decided_by: str | None = None
    rationale: str | None = None
    source_annotation_ids: list[str] = Field(default_factory=list)
    created_at: datetime

    @field_validator("decision_id", "trial_id", "experiment_id", "task_id")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)

    @field_validator("categories", "source_annotation_ids")
    @classmethod
    def validate_string_lists(cls, value: list[str]) -> list[str]:
        return [ensure_non_empty_string(item) for item in value]

    @field_validator("decided_by", "rationale")
    @classmethod
    def validate_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return ensure_non_empty_string(value)

    @model_validator(mode="after")
    def validate_resolution(self) -> AdjudicationRecord:
        if self.status is AdjudicationStatus.ADJUDICATED:
            if self.final_judgment is None or self.decided_by is None:
                msg = "adjudicated records require final_judgment and decided_by"
                raise ValueError(msg)
        return self


class FeedbackItem(StrictModel):
    item_id: str
    trial_id: str
    experiment_id: str
    task_id: str
    task_visibility: Visibility
    item_type: FeedbackItemType
    status: FeedbackItemStatus
    title: str
    summary: str
    categories: list[str] = Field(default_factory=list)
    source_annotation_ids: list[str] = Field(default_factory=list)
    adjudication_status: AdjudicationStatus
    created_at: datetime

    @field_validator("item_id", "trial_id", "experiment_id", "task_id", "title", "summary")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        return ensure_non_empty_string(value)

    @field_validator("categories", "source_annotation_ids")
    @classmethod
    def validate_string_lists(cls, value: list[str]) -> list[str]:
        return [ensure_non_empty_string(item) for item in value]


def parse_categories(raw_value: str) -> list[str]:
    """Split a comma-separated category string into a cleaned list."""
    return [category.strip() for category in raw_value.split(",") if category.strip()]


class EvaluationFeedbackHandoff(StrictModel):
    annotations: list[Annotation]
    confidence: ConfidenceMetadata
    adjudication: AdjudicationRecord | None = None
