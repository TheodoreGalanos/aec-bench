# ABOUTME: Defines the provider-free preregistration contract for AVO qualification.
# ABOUTME: Binds the one-shot baseline, final AVO, fixed evidence splits, budgets, and measures.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self, TypeVar

from pydantic import Field, FiniteFloat, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.commitments import validate_sha256
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

EF03_BASELINE_SOURCE_REVISION = "0bbb5bcfa6a452b7fd6e8c7ff44235d0adbfd9e8"
EF03_BASELINE_SOURCE_PATH = "src/aec_bench/evolution/variation.py"
EF03_BASELINE_SOURCE_SHA256 = "b7917c755d6e9cc4674f24c94adbee5807e1a982c60df51290628c3454f5a075"

MeasureT = TypeVar("MeasureT", bound=StrEnum)


class AVOQualificationSplitName(StrEnum):
    """The three fixed evidence roles in one AVO qualification."""

    DEVELOPMENT = "development"
    HOST_SELECTION = "host_selection"
    QUALIFICATION = "qualification"


class AVOProcessMeasure(StrEnum):
    """Work and terminal-state measures that do not claim benchmark improvement."""

    MODEL_REQUESTS = "model_requests"
    TOOL_CALLS = "tool_calls"
    DEVELOPMENT_EVALUATIONS = "development_evaluations"
    ELAPSED_SECONDS = "elapsed_seconds"
    KNOWN_COST_USD = "known_cost_usd"
    VALID_INTERNAL_ATTEMPTS = "valid_internal_attempts"
    INVALID_INTERNAL_ATTEMPTS = "invalid_internal_attempts"
    SUPERVISOR_INTERVENTIONS = "supervisor_interventions"
    SUBMISSIONS = "submissions"
    ABSTENTIONS = "abstentions"
    EXHAUSTED_CALLS = "exhausted_calls"


class AVOOutcomeMeasure(StrEnum):
    """Outcome measures reported separately from process accounting."""

    HOST_SELECTION_IMPROVEMENT = "host_selection_improvement"
    SEALED_QUALIFICATION_IMPROVEMENT = "sealed_qualification_improvement"
    VALIDITY_RATE = "validity_rate"
    DISCIPLINE_COVERAGE = "discipline_coverage"
    QD_COVERAGE = "qd_coverage"
    RUN_TO_RUN_VARIANCE = "run_to_run_variance"


class AVOQualificationBaselineReference(FrozenStrictModel):
    """Immutable source reference for the merged EF-03 one-shot baseline.

    The values are evidence recorded by the protocol author. Validation checks
    their shape and pinned identity only; it does not invoke Git or read a
    source checkout.
    """

    implementation: Literal["ef03_one_shot"] = "ef03_one_shot"
    source_revision: NonEmptyStr = EF03_BASELINE_SOURCE_REVISION
    source_path: NonEmptyStr = EF03_BASELINE_SOURCE_PATH
    source_sha256: str = EF03_BASELINE_SOURCE_SHA256

    @field_validator("source_revision")
    @classmethod
    def validate_source_revision(cls, value: str) -> str:
        if value != EF03_BASELINE_SOURCE_REVISION:
            raise ValueError("baseline source revision must be the merged EF-03 revision")
        return value

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        if value != EF03_BASELINE_SOURCE_PATH:
            raise ValueError("baseline source path must identify the EF-03 one-shot variation module")
        return value

    @field_validator("source_sha256")
    @classmethod
    def validate_source_sha256(cls, value: str) -> str:
        validate_sha256(value)
        if value != EF03_BASELINE_SOURCE_SHA256:
            raise ValueError("baseline source digest does not match the pinned EF-03 source")
        return value


class AVOQualificationRoute(FrozenStrictModel):
    """Exact model, provider, and provider route shared by both arms."""

    model: NonEmptyStr
    provider: NonEmptyStr
    route: NonEmptyStr


class AVOQualificationSplit(FrozenStrictModel):
    """One immutable task-set reference with an explicit visibility role."""

    name: AVOQualificationSplitName
    visibility: Visibility
    task_set_id: NonEmptyStr
    task_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    task_set_sha256: str

    @field_validator("task_refs")
    @classmethod
    def validate_task_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("qualification split task refs must be sorted and unique")
        return value

    @field_validator("task_set_sha256")
    @classmethod
    def validate_task_set_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_visibility(self) -> Self:
        expected = Visibility.HOLDOUT if self.name is AVOQualificationSplitName.QUALIFICATION else Visibility.PUBLIC
        if self.visibility is not expected:
            raise ValueError(f"{self.name.value} split must use {expected.value} visibility")
        return self


class AVOQualificationOuterBudget(FrozenStrictModel):
    """Full outer search configuration that must be common to both arms."""

    max_cycles: PositiveInt
    batch_size: PositiveInt
    improvement_threshold: FiniteFloat
    stagnation_window: PositiveInt
    structural_weight: FiniteFloat
    strategy: Literal["hill_climb", "qd"]


class AVOQualificationInnerBudget(FrozenStrictModel):
    """All hard limits for one bounded AVO call."""

    max_model_requests: PositiveInt
    max_tool_calls: PositiveInt
    max_development_evaluations: PositiveInt
    max_input_tokens: PositiveInt | None = None
    max_output_tokens: PositiveInt | None = None
    max_elapsed_seconds: FiniteFloat = Field(gt=0)
    max_consecutive_evaluation_errors: PositiveInt
    max_stagnant_evaluations: PositiveInt
    max_supervisor_interventions: NonNegativeInt = 0
    max_cost_usd: FiniteFloat | None = Field(default=None, gt=0)


class AVOQualificationArm(FrozenStrictModel):
    """One complete arm configuration in the paired qualification."""

    condition: Literal["ef03_one_shot", "avo"]
    route: AVOQualificationRoute
    outer_budget: AVOQualificationOuterBudget
    development: AVOQualificationSplit
    host_selection: AVOQualificationSplit
    qualification: AVOQualificationSplit
    inner_budget: AVOQualificationInnerBudget | None = None
    adaptive_feedback: tuple[Literal["development"], ...] = ("development",)
    baseline: AVOQualificationBaselineReference | None = None

    @field_validator("adaptive_feedback")
    @classmethod
    def validate_adaptive_feedback(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("adaptive feedback split names must be unique")
        if value != tuple(sorted(value)):
            raise ValueError("adaptive feedback split names must be canonical")
        return value

    @model_validator(mode="after")
    def validate_arm_shape(self) -> Self:
        expected_splits = (
            AVOQualificationSplitName.DEVELOPMENT,
            AVOQualificationSplitName.HOST_SELECTION,
            AVOQualificationSplitName.QUALIFICATION,
        )
        actual_splits = (self.development.name, self.host_selection.name, self.qualification.name)
        if actual_splits != expected_splits:
            raise ValueError("qualification arm must declare development, host_selection, and qualification splits")

        task_sets = (
            set(self.development.task_refs),
            set(self.host_selection.task_refs),
            set(self.qualification.task_refs),
        )
        if any(left.intersection(right) for index, left in enumerate(task_sets) for right in task_sets[index + 1 :]):
            raise ValueError("qualification split task refs must be disjoint")

        if self.condition == "ef03_one_shot":
            if self.inner_budget is not None:
                raise ValueError("one-shot baseline must not declare an AVO inner budget")
            if self.baseline is None:
                raise ValueError("one-shot baseline must declare its immutable source reference")
            if self.adaptive_feedback:
                raise ValueError("one-shot baseline must not declare adaptive feedback")
        else:
            if self.inner_budget is None:
                raise ValueError("AVO arm must declare an explicit inner budget")
            if self.baseline is not None:
                raise ValueError("AVO arm must not carry the one-shot baseline reference")
            if self.adaptive_feedback != (AVOQualificationSplitName.DEVELOPMENT.value,):
                raise ValueError("AVO adaptive feedback must use development material only")
        if AVOQualificationSplitName.QUALIFICATION.value in self.adaptive_feedback:
            raise ValueError("sealed qualification split must not enter adaptive feedback")
        return self


class AVOQualificationProtocol(LegacyContentAddressedModel):
    """Immutable provider-free plan for a later AVO versus EF-03 comparison."""

    schema_version: Literal["aecbench.avo-qualification-protocol.v1"] = "aecbench.avo-qualification-protocol.v1"
    protocol_id: NonEmptyStr
    baseline: AVOQualificationArm
    avo: AVOQualificationArm
    independent_seeds: tuple[NonNegativeInt, ...] = Field(min_length=1)
    repetitions_per_seed: PositiveInt = 1
    process_measures: tuple[AVOProcessMeasure, ...] = tuple(AVOProcessMeasure)
    outcome_measures: tuple[AVOOutcomeMeasure, ...] = tuple(AVOOutcomeMeasure)

    @field_validator("independent_seeds")
    @classmethod
    def validate_independent_seeds(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(isinstance(seed, bool) for seed in value):
            raise ValueError("independent seeds must be integers")
        if value != tuple(sorted(set(value))):
            raise ValueError("independent seeds must be sorted and unique")
        return value

    @field_validator("process_measures")
    @classmethod
    def validate_process_measures(cls, value: tuple[AVOProcessMeasure, ...]) -> tuple[AVOProcessMeasure, ...]:
        return _validate_complete_measure_set(value, AVOProcessMeasure, label="process")

    @field_validator("outcome_measures")
    @classmethod
    def validate_outcome_measures(cls, value: tuple[AVOOutcomeMeasure, ...]) -> tuple[AVOOutcomeMeasure, ...]:
        return _validate_complete_measure_set(value, AVOOutcomeMeasure, label="outcome")

    @model_validator(mode="after")
    def validate_protocol_identity(self) -> Self:
        if len(self.independent_seeds) * self.repetitions_per_seed < 2:
            raise ValueError("qualification protocol requires at least two independent total runs")
        if self.baseline.condition != "ef03_one_shot" or self.avo.condition != "avo":
            raise ValueError("qualification protocol must contain one EF-03 baseline arm and one AVO arm")
        if self.baseline.route != self.avo.route:
            raise ValueError("baseline and AVO must use the same model, provider, and route")
        if self.baseline.outer_budget != self.avo.outer_budget:
            raise ValueError("baseline and AVO must use the same full outer budget")
        for field_name in ("development", "host_selection", "qualification"):
            if getattr(self.baseline, field_name) != getattr(self.avo, field_name):
                raise ValueError(f"baseline and AVO must use the same {field_name} split")
        return self


def _validate_complete_measure_set(
    value: tuple[MeasureT, ...],
    measure_type: type[MeasureT],
    *,
    label: str,
) -> tuple[MeasureT, ...]:
    expected = tuple(measure_type)
    if value != expected:
        raise ValueError(f"{label} measures must contain the complete canonical measure set")
    return value


__all__ = (
    "AVOOutcomeMeasure",
    "AVOProcessMeasure",
    "AVOQualificationArm",
    "AVOQualificationBaselineReference",
    "AVOQualificationInnerBudget",
    "AVOQualificationOuterBudget",
    "AVOQualificationProtocol",
    "AVOQualificationRoute",
    "AVOQualificationSplit",
    "AVOQualificationSplitName",
    "EF03_BASELINE_SOURCE_PATH",
    "EF03_BASELINE_SOURCE_REVISION",
    "EF03_BASELINE_SOURCE_SHA256",
)
