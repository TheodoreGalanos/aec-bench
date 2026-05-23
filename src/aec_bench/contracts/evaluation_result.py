# ABOUTME: Contract models for evaluation output consumed by communication and feedback.
# ABOUTME: Defines validity, taxonomy, confidence, annotations, and the scored-result envelope.

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.validators import (
    NonEmptyStr,
    StrictModel,
    ensure_optional_non_empty_string,
)


class ErrorSource(StrEnum):
    MECHANICAL = "mechanical"
    HUMAN = "human"
    JUDGE = "judge"


class Judgment(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    DEFER = "defer"


class ValidityCheck(StrictModel):
    output_parseable: bool
    schema_valid: bool
    verifier_completed: bool
    errors: list[str] = Field(default_factory=list)


class ErrorTag(StrictModel):
    category: NonEmptyStr
    description: str | None = None
    source: ErrorSource


class ConfidenceMetadata(StrictModel):
    annotator_count: NonNegativeInt | None = None
    inter_rater_agreement: float | None = None
    confidence_interval: tuple[float, float] | None = None
    confidence_method: str | None = None

    @field_validator("inter_rater_agreement")
    @classmethod
    def validate_inter_rater_agreement(cls, value: float | None) -> float | None:
        if value is not None and not 0.0 <= value <= 1.0:
            msg = "inter_rater_agreement must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value

    @field_validator("confidence_interval")
    @classmethod
    def validate_confidence_interval(cls, value: tuple[float, float] | None) -> tuple[float, float] | None:
        if value is None:
            return None
        low, high = value
        if low > high:
            msg = "confidence_interval low bound must not exceed high bound"
            raise ValueError(msg)
        return value

    @field_validator("confidence_method")
    @classmethod
    def validate_confidence_method(cls, value: str | None) -> str | None:
        return ensure_optional_non_empty_string(value)


class Annotation(StrictModel):
    reviewer_id: NonEmptyStr
    reviewer_discipline: str | None = None
    timestamp: datetime
    judgment: Judgment
    categories: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("reviewer_discipline")
    @classmethod
    def validate_optional_discipline(cls, value: str | None) -> str | None:
        return ensure_optional_non_empty_string(value)


class EvaluationResult(StrictModel):
    reward: float
    validity: ValidityCheck
    breakdown: dict[str, Any] | None = None
    error_taxonomy: list[ErrorTag] | None = None
    confidence: ConfidenceMetadata | None = None
    annotations: list[Annotation] | None = None

    @field_validator("reward")
    @classmethod
    def validate_reward(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            msg = "reward must be between 0.0 and 1.0"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_parseability_reward(self) -> "EvaluationResult":
        if not self.validity.output_parseable and self.reward > 0.0:
            msg = "unparseable outputs must have reward 0.0"
            raise ValueError(msg)
        return self
