# ABOUTME: Defines persisted authored contracts for finite Learning Studies.
# ABOUTME: Keeps study roles and relations separate from task execution semantics.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class StudyClaimMode(StrEnum):
    DESCRIPTIVE = "descriptive"
    CONTROLLED = "controlled"


class ExperienceRole(StrEnum):
    ACQUISITION = "acquisition"
    PRACTICE = "practice"
    INTERFERENCE = "interference"
    PROBE = "probe"


class StudyArmRole(StrEnum):
    CONTROL = "control"
    EXPOSURE = "exposure"


class ExperienceRelationPurpose(StrEnum):
    TRANSFER = "transfer"
    BOUNDARY = "boundary"
    COMPOSITION = "composition"
    RETENTION = "retention"
    INTERFERENCE = "interference"


class LearningMeasurementKind(StrEnum):
    TRANSFER_GAIN = "transfer_gain"
    BOUNDARY_GAIN = "boundary_gain"
    COMPOSITION_GAIN = "composition_gain"
    RETAINED_GAIN = "retained_gain"
    RETENTION_DECAY = "retention_decay"
    INTERFERENCE_EFFECT = "interference_effect"
    LEARNING_EFFICIENCY = "learning_efficiency"


class ImprovementDirection(StrEnum):
    HIGHER = "higher"
    LOWER = "lower"


class LearningMeasurementSpec(FrozenStrictModel):
    measurement_id: NonEmptyStr
    kind: LearningMeasurementKind
    projection_id: NonEmptyStr
    direction: ImprovementDirection
    target_experience_id: NonEmptyStr
    focal_arm_id: NonEmptyStr
    comparator_arm_id: str | None = None
    reference_experience_id: str | None = None
    acquisition_experience_ids: tuple[NonEmptyStr, ...] = ()
    efficiency_denominator_id: str | None = None


class LearningExperienceSpec(FrozenStrictModel):
    experience_id: NonEmptyStr
    task_id: NonEmptyStr
    role: ExperienceRole
    description: str | None = None


class RunExperienceStep(FrozenStrictModel):
    kind: Literal["run_experience"] = "run_experience"
    step_id: NonEmptyStr
    experience_id: NonEmptyStr
    commit_post_state: bool | None = None


class ReleaseFeedbackStep(FrozenStrictModel):
    kind: Literal["release_feedback"] = "release_feedback"
    step_id: NonEmptyStr
    source_experience_id: NonEmptyStr
    feedback_view_id: NonEmptyStr


class ConsolidateStep(FrozenStrictModel):
    kind: Literal["consolidate"] = "consolidate"
    step_id: NonEmptyStr
    feedback_step_ids: tuple[NonEmptyStr, ...]
    operation_id: NonEmptyStr

    @field_validator("feedback_step_ids")
    @classmethod
    def validate_feedback_inputs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("consolidation requires at least one feedback step")
        if len(value) != len(set(value)):
            raise ValueError("consolidation feedback step ids must be unique")
        return value


LearningStudyStep = Annotated[
    RunExperienceStep | ReleaseFeedbackStep | ConsolidateStep,
    Field(discriminator="kind"),
]


class LearningArmSpec(FrozenStrictModel):
    arm_id: NonEmptyStr
    role: StudyArmRole
    treatment_id: NonEmptyStr
    steps: tuple[LearningStudyStep, ...]

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, value: tuple[LearningStudyStep, ...]) -> tuple[LearningStudyStep, ...]:
        if not value:
            raise ValueError("learning arm requires at least one step")
        step_ids = [step.step_id for step in value]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("learning arm step ids must be unique")
        return value


class ExperienceRelationSpec(FrozenStrictModel):
    relation_id: NonEmptyStr
    purpose: ExperienceRelationPurpose
    source_experience_ids: tuple[NonEmptyStr, ...]
    target_experience_id: NonEmptyStr
    invariant_claims: tuple[NonEmptyStr, ...]
    changed_dimensions: tuple[NonEmptyStr, ...]
    rationale: NonEmptyStr

    @model_validator(mode="after")
    def validate_shape(self) -> ExperienceRelationSpec:
        if not self.source_experience_ids:
            raise ValueError("experience relation requires at least one source")
        if len(self.source_experience_ids) != len(set(self.source_experience_ids)):
            raise ValueError("experience relation sources must be unique")
        if self.target_experience_id in self.source_experience_ids:
            raise ValueError("experience relation target must differ from its sources")
        if self.purpose is ExperienceRelationPurpose.COMPOSITION:
            if len(self.source_experience_ids) < 2:
                raise ValueError("composition relation requires at least two sources")
        elif len(self.source_experience_ids) != 1:
            raise ValueError(f"{self.purpose.value} relation requires exactly one source")
        if self.purpose in {ExperienceRelationPurpose.TRANSFER, ExperienceRelationPurpose.COMPOSITION}:
            if not self.invariant_claims:
                raise ValueError(f"{self.purpose.value} relation requires an invariant claim")
        if not self.changed_dimensions:
            raise ValueError("experience relation requires at least one changed dimension")
        if len(self.changed_dimensions) != len(set(self.changed_dimensions)):
            raise ValueError("experience relation changed dimensions must be unique")
        return self


class LearningStudySpec(FrozenStrictModel):
    study_id: NonEmptyStr
    title: NonEmptyStr
    research_question: NonEmptyStr
    claim_mode: StudyClaimMode
    agent: AgentConfig
    compute: ComputeConfig
    repetitions: PositiveInt = 1
    experiences: tuple[LearningExperienceSpec, ...]
    relations: tuple[ExperienceRelationSpec, ...] = ()
    measurements: tuple[LearningMeasurementSpec, ...] = ()
    arms: tuple[LearningArmSpec, ...]

    @model_validator(mode="after")
    def validate_identities(self) -> LearningStudySpec:
        _require_unique("experience", [item.experience_id for item in self.experiences])
        _require_unique("relation", [item.relation_id for item in self.relations])
        _require_unique("measurement", [item.measurement_id for item in self.measurements])
        _require_unique("arm", [item.arm_id for item in self.arms])
        if not self.experiences:
            raise ValueError("learning study requires at least one experience")
        if not self.arms:
            raise ValueError("learning study requires at least one arm")
        return self


def _require_unique(label: str, values: list[str]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"learning study {label} ids must be unique")


__all__ = (
    "ConsolidateStep",
    "ExperienceRelationPurpose",
    "ExperienceRelationSpec",
    "ExperienceRole",
    "LearningArmSpec",
    "LearningExperienceSpec",
    "LearningMeasurementKind",
    "LearningMeasurementSpec",
    "LearningStudySpec",
    "LearningStudyStep",
    "ReleaseFeedbackStep",
    "RunExperienceStep",
    "StudyArmRole",
    "StudyClaimMode",
    "ImprovementDirection",
)
