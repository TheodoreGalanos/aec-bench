# ABOUTME: Defines persisted pair-level results for Learning Study assessment.
# ABOUTME: Keeps controlled-comparison validity separate from task-owned outcome projections.

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from pydantic import NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


@dataclass(frozen=True)
class ProjectionResult:
    """One task-owned outcome projection for a learning-study measurement."""

    eligible: bool
    value: float | None
    reason: str | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None

    def __post_init__(self) -> None:
        if self.eligible:
            if self.value is None or not math.isfinite(self.value):
                raise ValueError("eligible outcome projection requires one finite value")
            if self.reason is not None:
                raise ValueError("eligible outcome projection cannot contain an exclusion reason")
        elif self.value is not None or not self.reason:
            raise ValueError("ineligible outcome projection requires one reason and no value")
        for bound in (self.lower_bound, self.upper_bound):
            if bound is not None and not math.isfinite(bound):
                raise ValueError("outcome projection bounds must be finite")
        if self.lower_bound is not None and self.upper_bound is not None and self.lower_bound > self.upper_bound:
            raise ValueError("outcome projection lower bound cannot exceed its upper bound")


class LearningComparisonValidity(StrEnum):
    CONTROLLED = "controlled"
    DESCRIPTIVE_ONLY = "descriptive_only"
    INVALID = "invalid"


class PairedMeasurementValue(FrozenStrictModel):
    repetition: NonNegativeInt
    focal_trial_id: NonEmptyStr
    comparator_trial_id: str | None
    focal_value: float
    comparator_value: float | None
    normalised_effect: float

    @field_validator("focal_value", "comparator_value", "normalised_effect")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("measurement values must be finite")
        return value


class ExcludedPair(FrozenStrictModel):
    repetition: NonNegativeInt
    reasons: tuple[NonEmptyStr, ...]

    @field_validator("reasons")
    @classmethod
    def validate_reasons(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("excluded pair requires at least one reason")
        return value


class LearningMeasurementResult(FrozenStrictModel):
    measurement_id: NonEmptyStr
    validity: LearningComparisonValidity
    projection_id: NonEmptyStr
    included_pairs: tuple[PairedMeasurementValue, ...]
    excluded_repetitions: tuple[ExcludedPair, ...]
    focal_mean: float | None
    comparator_mean: float | None
    mean_effect: float | None
    diagnostics: tuple[str, ...]

    @model_validator(mode="after")
    def validate_aggregates(self) -> LearningMeasurementResult:
        aggregate_values = (
            self.focal_mean,
            self.comparator_mean,
            self.mean_effect,
        )
        if any(value is not None and not math.isfinite(value) for value in aggregate_values):
            raise ValueError("measurement aggregates must be finite")
        return self


class LearningStudyAssessment(FrozenStrictModel):
    study_run_id: NonEmptyStr
    measurements: tuple[LearningMeasurementResult, ...]


__all__ = (
    "ExcludedPair",
    "LearningComparisonValidity",
    "LearningMeasurementResult",
    "LearningStudyAssessment",
    "PairedMeasurementValue",
    "ProjectionResult",
)
