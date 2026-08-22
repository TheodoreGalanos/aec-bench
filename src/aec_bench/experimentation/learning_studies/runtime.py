# ABOUTME: Coordinates finite Learning Study arms through caller-supplied operations.
# ABOUTME: Enforces copy-on-write learner state and probe isolation without knowing an execution family.

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Generic, TypeVar

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.planning import (
    CompiledConsolidationStep,
    CompiledExperienceStep,
    CompiledFeedbackStep,
    CompiledLearningStudy,
    PlannedArmRun,
)

StateT = TypeVar("StateT")
FeedbackT = TypeVar("FeedbackT")
MaybeAwaitable = TypeVar("MaybeAwaitable")


class ArmRunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class StepExecutionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class LearnerStateHandle(Generic[StateT]):
    state_id: str
    value: StateT


@dataclass(frozen=True)
class FeedbackHandle(Generic[FeedbackT]):
    feedback_id: str
    source_experience_id: str
    view_id: str
    value: FeedbackT


@dataclass(frozen=True)
class InitialiseLearnerRequest:
    study_run_id: str
    arm_run_id: str
    arm_id: str
    treatment_id: str
    repetition: int
    agent: AgentConfig
    compute: ComputeConfig
    working_root: Path | None


@dataclass(frozen=True)
class ExecuteExperienceRequest(Generic[StateT, FeedbackT]):
    arm_run: PlannedArmRun
    step: CompiledExperienceStep
    state: LearnerStateHandle[StateT]
    completed_trial_records: tuple[TrialRecord, ...]
    released_feedback: tuple[FeedbackHandle[FeedbackT], ...]


@dataclass(frozen=True)
class ReleaseFeedbackRequest(Generic[StateT]):
    arm_run: PlannedArmRun
    step: CompiledFeedbackStep
    state: LearnerStateHandle[StateT]
    source_trial_record: TrialRecord


@dataclass(frozen=True)
class ConsolidationRequest(Generic[StateT, FeedbackT]):
    arm_run: PlannedArmRun
    step: CompiledConsolidationStep
    state: LearnerStateHandle[StateT]
    feedback: tuple[FeedbackHandle[FeedbackT], ...]


@dataclass(frozen=True)
class ExperienceExecutionResult(Generic[StateT]):
    trial_record: TrialRecord
    candidate_state: LearnerStateHandle[StateT]
    changed_channels: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeedbackReleaseResult(Generic[StateT, FeedbackT]):
    candidate_state: LearnerStateHandle[StateT]
    feedback: FeedbackHandle[FeedbackT]
    changed_channels: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class LearnerTransitionResult(Generic[StateT]):
    candidate_state: LearnerStateHandle[StateT]
    changed_channels: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class StudyStepFailure:
    category: str
    message: str
    arm_run_id: str
    step_id: str | None


@dataclass(frozen=True)
class StepExecutionResult(Generic[FeedbackT]):
    step_id: str
    step_index: int
    kind: str
    status: StepExecutionStatus
    state_before_id: str | None
    candidate_state_id: str | None
    committed_state_id: str | None
    state_committed: bool | None
    changed_channels: tuple[str, ...] = ()
    trial_record: TrialRecord | None = None
    feedback: FeedbackHandle[FeedbackT] | None = None
    diagnostics: tuple[str, ...] = ()
    failure: StudyStepFailure | None = None


@dataclass(frozen=True)
class ArmRunExecutionResult(Generic[FeedbackT]):
    arm_run_id: str
    status: ArmRunStatus
    initial_state_id: str | None
    completed_steps: tuple[StepExecutionResult[FeedbackT], ...]
    trial_records: tuple[TrialRecord, ...]
    final_state_id: str | None
    failure: StudyStepFailure | None


@dataclass(frozen=True)
class LearningStudyExecution(Generic[FeedbackT]):
    study_run_id: str
    arm_runs: tuple[ArmRunExecutionResult[FeedbackT], ...]


@dataclass(frozen=True)
class LearningStudyOperations(Generic[StateT, FeedbackT]):
    initialise_learner: Callable[
        [InitialiseLearnerRequest],
        LearnerStateHandle[StateT] | Awaitable[LearnerStateHandle[StateT]],
    ]
    execute_experience: Callable[
        [ExecuteExperienceRequest[StateT, FeedbackT]],
        ExperienceExecutionResult[StateT] | Awaitable[ExperienceExecutionResult[StateT]],
    ]
    release_feedback: Callable[
        [ReleaseFeedbackRequest[StateT]],
        FeedbackReleaseResult[StateT, FeedbackT] | Awaitable[FeedbackReleaseResult[StateT, FeedbackT]],
    ]
    consolidate: Callable[
        [ConsolidationRequest[StateT, FeedbackT]],
        LearnerTransitionResult[StateT] | Awaitable[LearnerTransitionResult[StateT]],
    ]
    discard_state: Callable[[LearnerStateHandle[StateT]], None | Awaitable[None]]
    close_state: Callable[[LearnerStateHandle[StateT]], None | Awaitable[None]]


async def run_learning_study(
    *,
    plan: CompiledLearningStudy,
    operations: LearningStudyOperations[StateT, FeedbackT],
    working_root: Path | None = None,
) -> LearningStudyExecution[FeedbackT]:
    """Run isolated arm runs sequentially in the compiled interleaved order."""

    seen_state_ids: set[str] = set()
    seen_feedback_ids: set[str] = set()
    results: list[ArmRunExecutionResult[FeedbackT]] = []
    for arm_run in plan.arm_runs:
        results.append(
            await _run_arm_run(
                plan=plan,
                arm_run=arm_run,
                operations=operations,
                working_root=working_root,
                seen_state_ids=seen_state_ids,
                seen_feedback_ids=seen_feedback_ids,
            )
        )
    return LearningStudyExecution(study_run_id=plan.study_run_id, arm_runs=tuple(results))


async def _run_arm_run(
    *,
    plan: CompiledLearningStudy,
    arm_run: PlannedArmRun,
    operations: LearningStudyOperations[StateT, FeedbackT],
    working_root: Path | None,
    seen_state_ids: set[str],
    seen_feedback_ids: set[str],
) -> ArmRunExecutionResult[FeedbackT]:
    states_to_close: list[LearnerStateHandle[StateT]] = []
    completed_steps: list[StepExecutionResult[FeedbackT]] = []
    trial_records: list[TrialRecord] = []
    trials_by_experience: dict[str, TrialRecord] = {}
    feedback_by_step: dict[str, FeedbackHandle[FeedbackT]] = {}
    state: LearnerStateHandle[StateT] | None = None
    initial_state_id: str | None = None
    failure: StudyStepFailure | None = None
    try:
        try:
            state = await _maybe_await(
                operations.initialise_learner(
                    InitialiseLearnerRequest(
                        study_run_id=plan.study_run_id,
                        arm_run_id=arm_run.arm_run_id,
                        arm_id=arm_run.arm_id,
                        treatment_id=arm_run.treatment_id,
                        repetition=arm_run.repetition,
                        agent=plan.spec.agent,
                        compute=plan.spec.compute,
                        working_root=working_root,
                    )
                )
            )
            _validate_new_identity(state.state_id, seen_state_ids, "learner state")
            seen_state_ids.add(state.state_id)
            states_to_close.append(state)
            initial_state_id = state.state_id
        except asyncio.CancelledError:
            raise
        except Exception as error:
            failure = StudyStepFailure(
                category="learner-initialisation-failed",
                message=str(error),
                arm_run_id=arm_run.arm_run_id,
                step_id=None,
            )
            return ArmRunExecutionResult(
                arm_run_id=arm_run.arm_run_id,
                status=ArmRunStatus.FAILED,
                initial_state_id=None,
                completed_steps=(),
                trial_records=(),
                final_state_id=None,
                failure=failure,
            )

        for step_index, step in enumerate(arm_run.steps):
            assert state is not None
            state_before = state
            try:
                if isinstance(step, CompiledExperienceStep):
                    experience_result = await _maybe_await(
                        operations.execute_experience(
                            ExecuteExperienceRequest(
                                arm_run=arm_run,
                                step=step,
                                state=state_before,
                                completed_trial_records=tuple(trial_records),
                                released_feedback=tuple(feedback_by_step.values()),
                            )
                        )
                    )
                    _validate_trial_identity(experience_result.trial_record, step)
                    _validate_candidate(experience_result.candidate_state, state_before, seen_state_ids)
                    seen_state_ids.add(experience_result.candidate_state.state_id)
                    states_to_close.append(experience_result.candidate_state)
                    trial_records.append(experience_result.trial_record)
                    trials_by_experience[step.experience_id] = experience_result.trial_record
                    if step.commit_post_state:
                        state = experience_result.candidate_state
                    else:
                        await _maybe_await(operations.discard_state(experience_result.candidate_state))
                        state = state_before
                    completed_steps.append(
                        StepExecutionResult(
                            step_id=step.step_id,
                            step_index=step_index,
                            kind="run_experience",
                            status=StepExecutionStatus.COMPLETED,
                            state_before_id=state_before.state_id,
                            candidate_state_id=experience_result.candidate_state.state_id,
                            committed_state_id=state.state_id,
                            state_committed=step.commit_post_state,
                            changed_channels=experience_result.changed_channels,
                            trial_record=experience_result.trial_record,
                            diagnostics=experience_result.diagnostics,
                        )
                    )
                elif isinstance(step, CompiledFeedbackStep):
                    source = trials_by_experience.get(step.source_experience_id)
                    if source is None:
                        raise _StepFailure("feedback-source-missing", "feedback source did not complete in this arm")
                    feedback_result = await _maybe_await(
                        operations.release_feedback(
                            ReleaseFeedbackRequest(
                                arm_run=arm_run,
                                step=step,
                                state=state_before,
                                source_trial_record=source,
                            )
                        )
                    )
                    _validate_candidate(feedback_result.candidate_state, state_before, seen_state_ids)
                    _validate_new_identity(feedback_result.feedback.feedback_id, seen_feedback_ids, "feedback")
                    if feedback_result.feedback.source_experience_id != step.source_experience_id:
                        raise _StepFailure(
                            "feedback-release-failed", "feedback source identity does not match the plan"
                        )
                    if feedback_result.feedback.view_id != step.feedback_view_id:
                        raise _StepFailure("feedback-release-failed", "feedback view identity does not match the plan")
                    seen_state_ids.add(feedback_result.candidate_state.state_id)
                    seen_feedback_ids.add(feedback_result.feedback.feedback_id)
                    states_to_close.append(feedback_result.candidate_state)
                    state = feedback_result.candidate_state
                    feedback_by_step[step.step_id] = feedback_result.feedback
                    completed_steps.append(
                        StepExecutionResult(
                            step_id=step.step_id,
                            step_index=step_index,
                            kind="release_feedback",
                            status=StepExecutionStatus.COMPLETED,
                            state_before_id=state_before.state_id,
                            candidate_state_id=state.state_id,
                            committed_state_id=state.state_id,
                            state_committed=True,
                            changed_channels=feedback_result.changed_channels,
                            feedback=feedback_result.feedback,
                            diagnostics=feedback_result.diagnostics,
                        )
                    )
                elif isinstance(step, CompiledConsolidationStep):
                    selected_feedback = tuple(feedback_by_step[item] for item in step.feedback_step_ids)
                    transition_result = await _maybe_await(
                        operations.consolidate(
                            ConsolidationRequest(
                                arm_run=arm_run,
                                step=step,
                                state=state_before,
                                feedback=selected_feedback,
                            )
                        )
                    )
                    _validate_candidate(transition_result.candidate_state, state_before, seen_state_ids)
                    seen_state_ids.add(transition_result.candidate_state.state_id)
                    states_to_close.append(transition_result.candidate_state)
                    state = transition_result.candidate_state
                    completed_steps.append(
                        StepExecutionResult(
                            step_id=step.step_id,
                            step_index=step_index,
                            kind="consolidate",
                            status=StepExecutionStatus.COMPLETED,
                            state_before_id=state_before.state_id,
                            candidate_state_id=state.state_id,
                            committed_state_id=state.state_id,
                            state_committed=True,
                            changed_channels=transition_result.changed_channels,
                            diagnostics=transition_result.diagnostics,
                        )
                    )
                else:  # pragma: no cover - compiled union is closed.
                    raise _StepFailure("unsupported-step", f"unsupported step: {type(step).__name__}")
            except asyncio.CancelledError:
                raise
            except Exception as error:
                category = error.category if isinstance(error, _StepFailure) else _failure_category(step, error)
                failure = StudyStepFailure(
                    category=category,
                    message=str(error),
                    arm_run_id=arm_run.arm_run_id,
                    step_id=step.step_id,
                )
                completed_steps.append(
                    StepExecutionResult(
                        step_id=step.step_id,
                        step_index=step_index,
                        kind=_step_kind(step),
                        status=StepExecutionStatus.FAILED,
                        state_before_id=state_before.state_id,
                        candidate_state_id=None,
                        committed_state_id=state_before.state_id,
                        state_committed=False,
                        failure=failure,
                    )
                )
                for skipped_index, skipped in enumerate(arm_run.steps[step_index + 1 :], start=step_index + 1):
                    completed_steps.append(
                        StepExecutionResult(
                            step_id=skipped.step_id,
                            step_index=skipped_index,
                            kind=_step_kind(skipped),
                            status=StepExecutionStatus.SKIPPED,
                            state_before_id=state_before.state_id,
                            candidate_state_id=None,
                            committed_state_id=state_before.state_id,
                            state_committed=None,
                        )
                    )
                break
        return ArmRunExecutionResult(
            arm_run_id=arm_run.arm_run_id,
            status=ArmRunStatus.COMPLETED if failure is None else ArmRunStatus.FAILED,
            initial_state_id=initial_state_id,
            completed_steps=tuple(completed_steps),
            trial_records=tuple(trial_records),
            final_state_id=None if state is None else state.state_id,
            failure=failure,
        )
    finally:
        for handle in reversed(states_to_close):
            try:
                await _maybe_await(operations.close_state(handle))
            except asyncio.CancelledError:
                raise
            except Exception:
                pass


def _validate_trial_identity(record: TrialRecord, step: CompiledExperienceStep) -> None:
    if record.trial_id != step.trial.trial_id or record.task_id != step.trial.task_id:
        raise _StepFailure(
            "trial-record-mismatch",
            f"returned trial identity {(record.trial_id, record.task_id)!r} does not match "
            f"{(step.trial.trial_id, step.trial.task_id)!r}",
        )


def _validate_candidate(
    candidate: LearnerStateHandle[StateT],
    current: LearnerStateHandle[StateT],
    seen_state_ids: set[str],
) -> None:
    if candidate.state_id == current.state_id:
        raise _StepFailure("state-identity-reused", "state-producing operation reused the current state id")
    _validate_new_identity(candidate.state_id, seen_state_ids, "learner state")


def _validate_new_identity(value: str, seen: set[str], label: str) -> None:
    if not value.strip():
        raise _StepFailure("state-identity-reused", f"{label} id must not be blank")
    if value in seen:
        category = "arm-isolation-failed" if label == "learner state" else "feedback-release-failed"
        raise _StepFailure(category, f"{label} id was already used in this study: {value}")


def _failure_category(step: object, error: Exception) -> str:
    if isinstance(step, CompiledExperienceStep):
        return "state-discard-failed" if "discard" in str(error).lower() else "experience-execution-failed"
    if isinstance(step, CompiledFeedbackStep):
        return "feedback-release-failed"
    if isinstance(step, CompiledConsolidationStep):
        return "consolidation-failed"
    return "unsupported-step"


def _step_kind(step: object) -> str:
    if isinstance(step, CompiledExperienceStep):
        return "run_experience"
    if isinstance(step, CompiledFeedbackStep):
        return "release_feedback"
    if isinstance(step, CompiledConsolidationStep):
        return "consolidate"
    return "unsupported"


async def _maybe_await(value: MaybeAwaitable | Awaitable[MaybeAwaitable]) -> MaybeAwaitable:
    return await value if inspect.isawaitable(value) else value


class _StepFailure(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


__all__ = (
    "ArmRunExecutionResult",
    "ArmRunStatus",
    "ConsolidationRequest",
    "ExecuteExperienceRequest",
    "ExperienceExecutionResult",
    "FeedbackHandle",
    "FeedbackReleaseResult",
    "InitialiseLearnerRequest",
    "LearnerStateHandle",
    "LearnerTransitionResult",
    "LearningStudyExecution",
    "LearningStudyOperations",
    "ReleaseFeedbackRequest",
    "StepExecutionResult",
    "StepExecutionStatus",
    "StudyStepFailure",
    "run_learning_study",
)
