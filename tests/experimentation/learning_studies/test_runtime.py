# ABOUTME: Tests runtime-neutral Learning Study execution and copy-on-write isolation.
# ABOUTME: Proves probe discard, arm-local failure, and cross-arm identity controls.

from __future__ import annotations

from dataclasses import dataclass

import pytest

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import (
    ConsolidateStep,
    ExperienceRole,
    LearningArmSpec,
    LearningExperienceSpec,
    LearningStudySpec,
    ReleaseFeedbackStep,
    RunExperienceStep,
    StudyArmRole,
    StudyClaimMode,
)
from aec_bench.experimentation.learning_studies.planning import CompiledLearningStudy, compile_learning_study
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunStatus,
    ConsolidationRequest,
    ExecuteExperienceRequest,
    ExperienceExecutionResult,
    FeedbackHandle,
    FeedbackReleaseResult,
    InitialiseLearnerRequest,
    LearnerStateHandle,
    LearnerTransitionResult,
    LearningStudyOperations,
    ReleaseFeedbackRequest,
    StepExecutionStatus,
    run_learning_study,
)
from tests.support.trial_record_factories import make_trial_record


@dataclass(frozen=True)
class _Task:
    task_id: str


def _plan() -> CompiledLearningStudy:
    spec = LearningStudySpec(
        study_id="runtime-study",
        title="Runtime study",
        research_question="Does state remain isolated?",
        claim_mode=StudyClaimMode.CONTROLLED,
        agent=AgentConfig(name="agent", adapter="direct", model="fixed"),
        compute=ComputeConfig(backend="local"),
        experiences=(
            LearningExperienceSpec(experience_id="acquire", task_id="task/acquire", role=ExperienceRole.ACQUISITION),
            LearningExperienceSpec(experience_id="probe", task_id="task/probe", role=ExperienceRole.PROBE),
        ),
        arms=(
            LearningArmSpec(
                arm_id="cold",
                role=StudyArmRole.CONTROL,
                treatment_id="reset",
                steps=(RunExperienceStep(step_id="cold-probe", experience_id="probe"),),
            ),
            LearningArmSpec(
                arm_id="exposed",
                role=StudyArmRole.EXPOSURE,
                treatment_id="memory",
                steps=(
                    RunExperienceStep(step_id="acquire", experience_id="acquire"),
                    ReleaseFeedbackStep(
                        step_id="feedback",
                        source_experience_id="acquire",
                        feedback_view_id="public",
                    ),
                    ConsolidateStep(
                        step_id="consolidate",
                        feedback_step_ids=("feedback",),
                        operation_id="update-memory",
                    ),
                    RunExperienceStep(step_id="probe", experience_id="probe"),
                ),
            ),
        ),
    )
    return compile_learning_study(study_run_id="run-1", spec=spec, resolve_task=lambda task_id: _Task(task_id))


@pytest.mark.asyncio
async def test_runtime_commits_acquisition_and_discards_probe_state() -> None:
    counters = {"state": 0, "feedback": 0}
    discarded: list[str] = []
    requests: list[tuple[str, str]] = []

    def state(value: str) -> LearnerStateHandle[str]:
        counters["state"] += 1
        return LearnerStateHandle(state_id=f"state-{counters['state']}", value=value)

    def initialise(request: InitialiseLearnerRequest) -> LearnerStateHandle[str]:
        return state(f"initial:{request.arm_run_id}")

    async def execute(request: ExecuteExperienceRequest[str, str]) -> ExperienceExecutionResult[str]:
        requests.append((request.arm_run.arm_id, request.state.state_id))
        return ExperienceExecutionResult(
            trial_record=make_trial_record(
                trial_id=request.step.trial.trial_id,
                experiment_id=request.step.trial.experiment_id,
                task_id=request.step.trial.task_id,
            ),
            candidate_state=state(f"after:{request.step.experience_id}"),
            changed_channels=("memory",),
        )

    def release(request: ReleaseFeedbackRequest[str]) -> FeedbackReleaseResult[str, str]:
        counters["feedback"] += 1
        return FeedbackReleaseResult(
            candidate_state=state("feedback-visible"),
            feedback=FeedbackHandle(
                feedback_id=f"feedback-{counters['feedback']}",
                source_experience_id=request.step.source_experience_id,
                view_id=request.step.feedback_view_id,
                value="safe",
            ),
            changed_channels=("feedback",),
        )

    def consolidate(request: ConsolidationRequest[str, str]) -> LearnerTransitionResult[str]:
        assert [item.value for item in request.feedback] == ["safe"]
        return LearnerTransitionResult(candidate_state=state("memory-updated"), changed_channels=("memory",))

    operations = LearningStudyOperations(
        initialise_learner=initialise,
        execute_experience=execute,
        release_feedback=release,
        consolidate=consolidate,
        discard_state=lambda handle: discarded.append(handle.state_id),
        close_state=lambda _handle: None,
    )

    result = await run_learning_study(plan=_plan(), operations=operations)

    assert [arm.status for arm in result.arm_runs] == [ArmRunStatus.COMPLETED, ArmRunStatus.COMPLETED]
    assert len(discarded) == 2
    cold_probe = result.arm_runs[0].completed_steps[0]
    exposed_probe = result.arm_runs[1].completed_steps[-1]
    assert cold_probe.state_committed is False
    assert exposed_probe.state_committed is False
    assert cold_probe.committed_state_id == result.arm_runs[0].initial_state_id
    assert exposed_probe.committed_state_id != exposed_probe.candidate_state_id
    assert requests[0][0] == "cold"
    assert requests[-1][0] == "exposed"


@pytest.mark.asyncio
async def test_runtime_rejects_cross_arm_state_identity_and_continues() -> None:
    def initialise(_request: InitialiseLearnerRequest) -> LearnerStateHandle[str]:
        return LearnerStateHandle(state_id="shared-state", value="mutable-root")

    def execute(request: ExecuteExperienceRequest[str, str]) -> ExperienceExecutionResult[str]:
        return ExperienceExecutionResult(
            trial_record=make_trial_record(
                trial_id=request.step.trial.trial_id,
                experiment_id=request.step.trial.experiment_id,
                task_id=request.step.trial.task_id,
            ),
            candidate_state=LearnerStateHandle(state_id="cold-probe-candidate", value="candidate"),
        )

    operations = LearningStudyOperations(
        initialise_learner=initialise,
        execute_experience=execute,
        release_feedback=lambda _request: pytest.fail("not reached"),
        consolidate=lambda _request: pytest.fail("not reached"),
        discard_state=lambda _handle: None,
        close_state=lambda _handle: None,
    )

    result = await run_learning_study(plan=_plan(), operations=operations)

    assert result.arm_runs[0].status is ArmRunStatus.COMPLETED
    assert result.arm_runs[1].status is ArmRunStatus.FAILED
    assert result.arm_runs[1].failure is not None
    assert result.arm_runs[1].failure.category == "learner-initialisation-failed"
    assert "already used" in result.arm_runs[1].failure.message


@pytest.mark.asyncio
async def test_runtime_failure_keeps_previous_state_and_does_not_stop_later_arm() -> None:
    state_count = 0

    def initialise(request: InitialiseLearnerRequest) -> LearnerStateHandle[str]:
        nonlocal state_count
        state_count += 1
        return LearnerStateHandle(state_id=f"initial-{state_count}", value=request.arm_id)

    def execute(request: ExecuteExperienceRequest[str, str]) -> ExperienceExecutionResult[str]:
        if request.arm_run.arm_id == "cold":
            raise RuntimeError("adapter stopped before a TrialRecord")
        return ExperienceExecutionResult(
            trial_record=make_trial_record(
                trial_id=request.step.trial.trial_id,
                experiment_id=request.step.trial.experiment_id,
                task_id=request.step.trial.task_id,
            ),
            candidate_state=LearnerStateHandle(
                state_id=f"{request.arm_run.arm_id}-{request.step.step_id}",
                value="candidate",
            ),
        )

    operations = LearningStudyOperations(
        initialise_learner=initialise,
        execute_experience=execute,
        release_feedback=lambda request: FeedbackReleaseResult(
            candidate_state=LearnerStateHandle(state_id="exposed-feedback-state", value="feedback"),
            feedback=FeedbackHandle(
                feedback_id="exposed-feedback",
                source_experience_id=request.step.source_experience_id,
                view_id=request.step.feedback_view_id,
                value="safe",
            ),
        ),
        consolidate=lambda _request: LearnerTransitionResult(
            candidate_state=LearnerStateHandle(state_id="exposed-consolidated", value="memory"),
            changed_channels=("memory",),
        ),
        discard_state=lambda _handle: None,
        close_state=lambda _handle: None,
    )

    result = await run_learning_study(plan=_plan(), operations=operations)

    cold, exposed = result.arm_runs
    assert cold.status is ArmRunStatus.FAILED
    assert cold.completed_steps[0].status is StepExecutionStatus.FAILED
    assert cold.final_state_id == cold.initial_state_id
    assert exposed.status is ArmRunStatus.COMPLETED
    assert len(exposed.trial_records) == 2
