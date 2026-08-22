# ABOUTME: Defines persisted Learning Study state, transition, step, and event evidence.
# ABOUTME: Keeps learner history beside ordinary TrialRecords without adding fields to TrialRecord.

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import NonNegativeInt, model_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class StudyEventKind(StrEnum):
    STUDY_STARTED = "study_started"
    ARM_RUN_STARTED = "arm_run_started"
    LEARNER_INITIALISED = "learner_initialised"
    STEP_STARTED = "step_started"
    STEP_COMMITTED = "step_committed"
    STEP_FAILED = "step_failed"
    ARM_RUN_COMPLETED = "arm_run_completed"
    ARM_RUN_FAILED = "arm_run_failed"
    STUDY_COMPLETED = "study_completed"
    STUDY_CANCELLED = "study_cancelled"


class StudyStepStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class StudyRunStatus(StrEnum):
    COMPLETED = "completed"
    COMPLETED_WITH_FAILED_ARMS = "completed_with_failed_arms"


class LearnerStateRef(FrozenStrictModel):
    state_id: NonEmptyStr
    arm_run_id: NonEmptyStr
    treatment_id: NonEmptyStr
    parent_state_id: str | None
    created_after_step_id: str | None
    artifact: ArtifactRef

    @model_validator(mode="after")
    def validate_parent_shape(self) -> LearnerStateRef:
        if (self.parent_state_id is None) != (self.created_after_step_id is None):
            raise ValueError("learner state parent and creating step must be present together")
        return self


class FeedbackReleaseRecord(FrozenStrictModel):
    feedback_id: NonEmptyStr
    arm_run_id: NonEmptyStr
    release_step_id: NonEmptyStr
    source_experience_id: NonEmptyStr
    source_trial_id: NonEmptyStr
    view_id: NonEmptyStr
    public_artifact_refs: tuple[ArtifactRef, ...]
    state_before_id: NonEmptyStr
    state_after_id: NonEmptyStr


class LearnerTransitionReceipt(FrozenStrictModel):
    transition_id: NonEmptyStr
    arm_run_id: NonEmptyStr
    step_id: NonEmptyStr
    operation_kind: Literal[
        "initialise",
        "experience",
        "feedback_release",
        "consolidation",
        "probe_discard",
    ]
    state_before_id: str | None
    candidate_state_id: NonEmptyStr
    committed_state_id: str | None
    committed: bool
    feedback_ids: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_commit_shape(self) -> LearnerTransitionReceipt:
        if self.committed and self.committed_state_id != self.candidate_state_id:
            raise ValueError("committed transition must commit its candidate state")
        if not self.committed and self.state_before_id != self.committed_state_id:
            raise ValueError("discarded transition must preserve its prior committed state")
        return self


class StudyStepFailureRecord(FrozenStrictModel):
    category: NonEmptyStr
    message: str


class StudyStepReceipt(FrozenStrictModel):
    study_run_id: NonEmptyStr
    arm_run_id: NonEmptyStr
    step_id: NonEmptyStr
    step_index: NonNegativeInt
    step_kind: Literal["run_experience", "release_feedback", "consolidate"]
    status: StudyStepStatus
    trial_id: str | None = None
    feedback_id: str | None = None
    transition_id: str | None = None
    failure: StudyStepFailureRecord | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> StudyStepReceipt:
        if self.status is StudyStepStatus.COMPLETED and self.failure is not None:
            raise ValueError("completed step cannot contain a failure")
        if self.status is StudyStepStatus.FAILED and self.failure is None:
            raise ValueError("failed step requires failure evidence")
        return self


class StudyEvent(FrozenStrictModel):
    sequence: NonNegativeInt
    study_run_id: NonEmptyStr
    kind: StudyEventKind
    arm_run_id: str | None = None
    step_id: str | None = None
    reference: str | None = None


class RecordedArmRunResult(FrozenStrictModel):
    arm_run_id: NonEmptyStr
    status: Literal["completed", "failed"]
    initial_state_id: str | None
    final_state_id: str | None
    trial_ids: tuple[NonEmptyStr, ...]


class RecordedStudyExecution(FrozenStrictModel):
    study_run_id: NonEmptyStr
    status: StudyRunStatus
    arm_runs: tuple[RecordedArmRunResult, ...]


__all__ = (
    "FeedbackReleaseRecord",
    "LearnerStateRef",
    "LearnerTransitionReceipt",
    "RecordedArmRunResult",
    "RecordedStudyExecution",
    "StudyEvent",
    "StudyEventKind",
    "StudyRunStatus",
    "StudyStepFailureRecord",
    "StudyStepReceipt",
    "StudyStepStatus",
)
