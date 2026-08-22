# ABOUTME: Coordinates finite Learning Study arms through caller-supplied operations.
# ABOUTME: Enforces copy-on-write learner state, probe isolation, and receipt-based resume.

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import Generic, TypeVar

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.errors import LearningStudyPersistenceError
from aec_bench.experimentation.learning_studies.planning import (
    CompiledConsolidationStep,
    CompiledExperienceStep,
    CompiledFeedbackStep,
    CompiledLearningStudy,
    CompiledStudyStep,
    PlannedArmRun,
)

StateT = TypeVar("StateT")
FeedbackT = TypeVar("FeedbackT")
MaybeAwaitable = TypeVar("MaybeAwaitable")
OperationRequestT = TypeVar("OperationRequestT")
OperationResultT = TypeVar("OperationResultT")


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
class ExecuteExperienceRequest(Generic[StateT]):
    arm_run: PlannedArmRun
    step: CompiledExperienceStep
    state: LearnerStateHandle[StateT]


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


@dataclass(frozen=True)
class FeedbackReleaseResult(Generic[StateT, FeedbackT]):
    candidate_state: LearnerStateHandle[StateT]
    feedback: FeedbackHandle[FeedbackT]


@dataclass(frozen=True)
class LearnerTransitionResult(Generic[StateT]):
    candidate_state: LearnerStateHandle[StateT]


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
    trial_record: TrialRecord | None = None
    feedback: FeedbackHandle[FeedbackT] | None = None
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
class ArmRunResumeState(Generic[StateT, FeedbackT]):
    initial_state_id: str
    current_state: LearnerStateHandle[StateT]
    completed_steps: tuple[StepExecutionResult[FeedbackT], ...]
    trial_records: tuple[TrialRecord, ...]
    feedback_by_step: tuple[tuple[str, FeedbackHandle[FeedbackT]], ...]


@dataclass(frozen=True)
class LearningStudyResume(Generic[StateT, FeedbackT]):
    completed_arm_runs: Mapping[str, ArmRunExecutionResult[FeedbackT]]
    incomplete_arm_runs: Mapping[str, ArmRunResumeState[StateT, FeedbackT]]
    known_state_ids: frozenset[str]
    known_feedback_ids: frozenset[str]


class LearningStudyObserver(Generic[StateT, FeedbackT]):
    """Optional evidence boundary invoked around runtime commitment points."""

    def arm_started(self, arm_run: PlannedArmRun) -> None | Awaitable[None]:
        return None

    def learner_initialised(
        self,
        arm_run: PlannedArmRun,
        state: LearnerStateHandle[StateT],
    ) -> None | Awaitable[None]:
        return None

    def step_started(
        self,
        arm_run: PlannedArmRun,
        step: CompiledStudyStep,
        step_index: int,
    ) -> None | Awaitable[None]:
        return None

    def step_committed(
        self,
        arm_run: PlannedArmRun,
        step: CompiledStudyStep,
        result: StepExecutionResult[FeedbackT],
        state_before: LearnerStateHandle[StateT],
        candidate_state: LearnerStateHandle[StateT],
        committed_state: LearnerStateHandle[StateT],
    ) -> None | Awaitable[None]:
        return None

    def step_failed(
        self,
        arm_run: PlannedArmRun,
        step: CompiledStudyStep,
        result: StepExecutionResult[FeedbackT],
    ) -> None | Awaitable[None]:
        return None

    def arm_finished(self, result: ArmRunExecutionResult[FeedbackT]) -> None | Awaitable[None]:
        return None

    def study_finished(self, result: LearningStudyExecution[FeedbackT]) -> None | Awaitable[None]:
        return None

    def study_cancelled(self) -> None | Awaitable[None]:
        return None


@dataclass(frozen=True)
class LearningStudyOperations(Generic[StateT, FeedbackT]):
    initialise_learner: Callable[
        [PlannedArmRun],
        LearnerStateHandle[StateT] | Awaitable[LearnerStateHandle[StateT]],
    ]
    execute_experience: Callable[
        [ExecuteExperienceRequest[StateT]],
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


async def run_learning_study(
    *,
    plan: CompiledLearningStudy,
    operations: LearningStudyOperations[StateT, FeedbackT],
    observer: LearningStudyObserver[StateT, FeedbackT] | None = None,
    resume: LearningStudyResume[StateT, FeedbackT] | None = None,
) -> LearningStudyExecution[FeedbackT]:
    """Run isolated arm runs sequentially in the compiled interleaved order."""

    seen_state_ids = set(() if resume is None else resume.known_state_ids)
    seen_feedback_ids = set(() if resume is None else resume.known_feedback_ids)
    results: list[ArmRunExecutionResult[FeedbackT]] = []
    try:
        for arm_run in plan.arm_runs:
            terminal = None if resume is None else resume.completed_arm_runs.get(arm_run.arm_run_id)
            if terminal is not None:
                results.append(terminal)
                continue
            results.append(
                await _run_arm_run(
                    arm_run=arm_run,
                    operations=operations,
                    seen_state_ids=seen_state_ids,
                    seen_feedback_ids=seen_feedback_ids,
                    observer=observer,
                    resume_state=None if resume is None else resume.incomplete_arm_runs.get(arm_run.arm_run_id),
                )
            )
    except asyncio.CancelledError:
        if observer is not None:
            await _notify(observer.study_cancelled)
        raise
    execution = LearningStudyExecution(study_run_id=plan.study_run_id, arm_runs=tuple(results))
    if observer is not None:
        await _notify(partial(observer.study_finished, execution))
    return execution


async def _run_arm_run(
    *,
    arm_run: PlannedArmRun,
    operations: LearningStudyOperations[StateT, FeedbackT],
    seen_state_ids: set[str],
    seen_feedback_ids: set[str],
    observer: LearningStudyObserver[StateT, FeedbackT] | None,
    resume_state: ArmRunResumeState[StateT, FeedbackT] | None,
) -> ArmRunExecutionResult[FeedbackT]:
    completed_steps: list[StepExecutionResult[FeedbackT]] = []
    trial_records: list[TrialRecord] = []
    trials_by_experience: dict[str, TrialRecord] = {}
    feedback_by_step: dict[str, FeedbackHandle[FeedbackT]] = {}
    state: LearnerStateHandle[StateT] | None = None
    initial_state_id: str | None = None
    failure: StudyStepFailure | None = None
    step_start_index = 0
    if resume_state is None:
        if observer is not None:
            await _notify(partial(observer.arm_started, arm_run))
        try:
            initialised_state = await _call_operation(
                operations.initialise_learner,
                arm_run,
            )
            _validate_new_identity(initialised_state.state_id, seen_state_ids, "learner state")
            seen_state_ids.add(initialised_state.state_id)
            state = initialised_state
            initial_state_id = initialised_state.state_id
            if observer is not None:
                await _notify(partial(observer.learner_initialised, arm_run, initialised_state))
        except asyncio.CancelledError:
            raise
        except LearningStudyPersistenceError:
            raise
        except Exception as error:
            failure = StudyStepFailure(
                category="learner-initialisation-failed",
                message=str(error),
                arm_run_id=arm_run.arm_run_id,
                step_id=None,
            )
            arm_result: ArmRunExecutionResult[FeedbackT] = ArmRunExecutionResult(
                arm_run_id=arm_run.arm_run_id,
                status=ArmRunStatus.FAILED,
                initial_state_id=None,
                completed_steps=(),
                trial_records=(),
                final_state_id=None,
                failure=failure,
            )
            if observer is not None:
                await _notify(partial(observer.arm_finished, arm_result))
            return arm_result
    else:
        _validate_resume_prefix(arm_run, resume_state)
        state = resume_state.current_state
        initial_state_id = resume_state.initial_state_id
        completed_steps.extend(resume_state.completed_steps)
        trial_records.extend(resume_state.trial_records)
        feedback_by_step.update(resume_state.feedback_by_step)
        for completed_step in resume_state.completed_steps:
            if completed_step.trial_record is None:
                continue
            planned_step = arm_run.steps[completed_step.step_index]
            if not isinstance(planned_step, CompiledExperienceStep):
                raise LearningStudyPersistenceError("resumed trial does not match an experience step")
            trials_by_experience[planned_step.experience_id] = completed_step.trial_record
        step_start_index = len(resume_state.completed_steps)

    for step_index, step in enumerate(arm_run.steps[step_start_index:], start=step_start_index):
        assert state is not None
        state_before = state
        try:
            if observer is not None:
                await _notify(partial(observer.step_started, arm_run, step, step_index))
            if isinstance(step, CompiledExperienceStep):
                experience_result = await _call_operation(
                    operations.execute_experience,
                    ExecuteExperienceRequest(
                        arm_run=arm_run,
                        step=step,
                        state=state_before,
                    ),
                )
                _validate_trial_identity(experience_result.trial_record, step)
                _validate_candidate(experience_result.candidate_state, state_before, seen_state_ids)
                seen_state_ids.add(experience_result.candidate_state.state_id)
                trial_records.append(experience_result.trial_record)
                trials_by_experience[step.experience_id] = experience_result.trial_record
                if step.commit_post_state:
                    state = experience_result.candidate_state
                else:
                    await _call_operation(operations.discard_state, experience_result.candidate_state)
                    state = state_before
                step_result: StepExecutionResult[FeedbackT] = StepExecutionResult(
                    step_id=step.step_id,
                    step_index=step_index,
                    kind="run_experience",
                    status=StepExecutionStatus.COMPLETED,
                    state_before_id=state_before.state_id,
                    candidate_state_id=experience_result.candidate_state.state_id,
                    committed_state_id=state.state_id,
                    state_committed=step.commit_post_state,
                    trial_record=experience_result.trial_record,
                )
                candidate_state = experience_result.candidate_state
            elif isinstance(step, CompiledFeedbackStep):
                source = trials_by_experience.get(step.source_experience_id)
                if source is None:
                    raise _StepFailure("feedback-source-missing", "feedback source did not complete in this arm")
                feedback_result = await _call_operation(
                    operations.release_feedback,
                    ReleaseFeedbackRequest(
                        arm_run=arm_run,
                        step=step,
                        state=state_before,
                        source_trial_record=source,
                    ),
                )
                _validate_candidate(feedback_result.candidate_state, state_before, seen_state_ids)
                _validate_new_identity(feedback_result.feedback.feedback_id, seen_feedback_ids, "feedback")
                if feedback_result.feedback.source_experience_id != step.source_experience_id:
                    raise _StepFailure("feedback-release-failed", "feedback source identity does not match the plan")
                if feedback_result.feedback.view_id != step.feedback_view_id:
                    raise _StepFailure("feedback-release-failed", "feedback view identity does not match the plan")
                seen_state_ids.add(feedback_result.candidate_state.state_id)
                seen_feedback_ids.add(feedback_result.feedback.feedback_id)
                state = feedback_result.candidate_state
                feedback_by_step[step.step_id] = feedback_result.feedback
                step_result = StepExecutionResult(
                    step_id=step.step_id,
                    step_index=step_index,
                    kind="release_feedback",
                    status=StepExecutionStatus.COMPLETED,
                    state_before_id=state_before.state_id,
                    candidate_state_id=state.state_id,
                    committed_state_id=state.state_id,
                    state_committed=True,
                    feedback=feedback_result.feedback,
                )
                candidate_state = feedback_result.candidate_state
            elif isinstance(step, CompiledConsolidationStep):
                selected_feedback = tuple(feedback_by_step[item] for item in step.feedback_step_ids)
                transition_result = await _call_operation(
                    operations.consolidate,
                    ConsolidationRequest(
                        arm_run=arm_run,
                        step=step,
                        state=state_before,
                        feedback=selected_feedback,
                    ),
                )
                _validate_candidate(transition_result.candidate_state, state_before, seen_state_ids)
                seen_state_ids.add(transition_result.candidate_state.state_id)
                state = transition_result.candidate_state
                step_result = StepExecutionResult(
                    step_id=step.step_id,
                    step_index=step_index,
                    kind="consolidate",
                    status=StepExecutionStatus.COMPLETED,
                    state_before_id=state_before.state_id,
                    candidate_state_id=state.state_id,
                    committed_state_id=state.state_id,
                    state_committed=True,
                )
                candidate_state = transition_result.candidate_state
            else:  # pragma: no cover - compiled union is closed.
                raise _StepFailure("unsupported-step", f"unsupported step: {type(step).__name__}")
            if observer is not None:
                await _notify(
                    partial(
                        observer.step_committed,
                        arm_run,
                        step,
                        step_result,
                        state_before,
                        candidate_state,
                        state,
                    )
                )
            completed_steps.append(step_result)
        except asyncio.CancelledError:
            raise
        except LearningStudyPersistenceError:
            raise
        except Exception as error:
            category = error.category if isinstance(error, _StepFailure) else _failure_category(step, error)
            failure = StudyStepFailure(
                category=category,
                message=str(error),
                arm_run_id=arm_run.arm_run_id,
                step_id=step.step_id,
            )
            failed_step: StepExecutionResult[FeedbackT] = StepExecutionResult(
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
            if observer is not None:
                await _notify(partial(observer.step_failed, arm_run, step, failed_step))
            completed_steps.append(failed_step)
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
    arm_result = ArmRunExecutionResult[FeedbackT](
        arm_run_id=arm_run.arm_run_id,
        status=ArmRunStatus.COMPLETED if failure is None else ArmRunStatus.FAILED,
        initial_state_id=initial_state_id,
        completed_steps=tuple(completed_steps),
        trial_records=tuple(trial_records),
        final_state_id=None if state is None else state.state_id,
        failure=failure,
    )
    if observer is not None:
        await _notify(partial(observer.arm_finished, arm_result))
    return arm_result


def _validate_resume_prefix(
    arm_run: PlannedArmRun,
    resume_state: ArmRunResumeState[StateT, FeedbackT],
) -> None:
    if len(resume_state.completed_steps) >= len(arm_run.steps):
        raise LearningStudyPersistenceError("incomplete resume state contains a terminal arm")
    for index, completed in enumerate(resume_state.completed_steps):
        if completed.status is not StepExecutionStatus.COMPLETED:
            raise LearningStudyPersistenceError("resume prefix contains a non-completed step")
        if completed.step_index != index or completed.step_id != arm_run.steps[index].step_id:
            raise LearningStudyPersistenceError("resume step receipt does not match compiled plan order")


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


async def _notify(callback: Callable[[], None | Awaitable[None]]) -> None:
    try:
        await _maybe_await(callback())
    except asyncio.CancelledError:
        raise
    except LearningStudyPersistenceError:
        raise
    except Exception as error:
        raise LearningStudyPersistenceError(str(error)) from error


async def _maybe_await(value: MaybeAwaitable | Awaitable[MaybeAwaitable]) -> MaybeAwaitable:
    return await value if inspect.isawaitable(value) else value


async def _call_operation(
    callback: Callable[[OperationRequestT], OperationResultT | Awaitable[OperationResultT]],
    request: OperationRequestT,
) -> OperationResultT:
    result = await asyncio.to_thread(callback, request)
    return await result if inspect.isawaitable(result) else result


class _StepFailure(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


__all__ = (
    "ArmRunExecutionResult",
    "ArmRunResumeState",
    "ArmRunStatus",
    "ConsolidationRequest",
    "ExecuteExperienceRequest",
    "ExperienceExecutionResult",
    "FeedbackHandle",
    "FeedbackReleaseResult",
    "LearnerStateHandle",
    "LearnerTransitionResult",
    "LearningStudyExecution",
    "LearningStudyObserver",
    "LearningStudyOperations",
    "LearningStudyResume",
    "ReleaseFeedbackRequest",
    "StepExecutionResult",
    "StepExecutionStatus",
    "StudyStepFailure",
    "run_learning_study",
)
