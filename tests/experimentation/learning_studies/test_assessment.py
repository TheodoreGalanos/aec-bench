# ABOUTME: Tests controlled Learning Study matching through named task-owned projections.
# ABOUTME: Keeps pair exclusions, descriptive downgrades, invalid evidence, and uncertainty visible.

from __future__ import annotations

from dataclasses import dataclass

import pytest

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import (
    ExperienceRole,
    ImprovementDirection,
    LearningArmSpec,
    LearningExperienceSpec,
    LearningMeasurementKind,
    LearningMeasurementSpec,
    LearningStudySpec,
    RunExperienceStep,
    StudyArmRole,
    StudyClaimMode,
)
from aec_bench.contracts.learning_study_assessment import LearningComparisonValidity
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.assessment import (
    AssessmentArmEvidence,
    ProjectionResult,
    assess_learning_study,
)
from aec_bench.experimentation.learning_studies.planning import (
    CompiledExperienceStep,
    CompiledLearningStudy,
    compile_learning_study,
)
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunExecutionResult,
    ArmRunStatus,
    LearningStudyExecution,
    StepExecutionResult,
    StepExecutionStatus,
)
from tests.support.trial_record_factories import make_trial_record


@dataclass(frozen=True)
class _Task:
    task_id: str


def _plan(
    *, repetitions: int = 2, direction: ImprovementDirection = ImprovementDirection.HIGHER
) -> CompiledLearningStudy:
    spec = LearningStudySpec(
        study_id="assessment-study",
        title="Assessment study",
        research_question="Does exposure change the matched probe?",
        claim_mode=StudyClaimMode.CONTROLLED,
        agent=AgentConfig(name="agent", adapter="direct", model="fixed"),
        compute=ComputeConfig(backend="local"),
        repetitions=repetitions,
        experiences=(
            LearningExperienceSpec(experience_id="acquire", task_id="task/acquire", role=ExperienceRole.ACQUISITION),
            LearningExperienceSpec(experience_id="probe", task_id="task/probe", role=ExperienceRole.PROBE),
        ),
        measurements=(
            LearningMeasurementSpec(
                measurement_id="transfer",
                kind=LearningMeasurementKind.TRANSFER_GAIN,
                projection_id="task-outcome",
                direction=direction,
                target_experience_id="probe",
                focal_arm_id="exposed",
                comparator_arm_id="cold",
                acquisition_experience_ids=("acquire",),
            ),
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
                    RunExperienceStep(step_id="probe", experience_id="probe"),
                ),
            ),
        ),
    )
    return compile_learning_study(
        study_run_id="assessment-run",
        spec=spec,
        resolve_task=lambda task_id: _Task(task_id),
    )


def _execution(plan: CompiledLearningStudy, rewards: dict[tuple[str, int], float]) -> LearningStudyExecution[object]:
    arm_results: list[ArmRunExecutionResult[object]] = []
    for arm_run in plan.arm_runs:
        steps: list[StepExecutionResult[object]] = []
        records = []
        for index, step in enumerate(arm_run.steps):
            assert isinstance(step, CompiledExperienceStep)
            reward = rewards[(arm_run.arm_id, arm_run.repetition)] if step.experience_id == "probe" else 1.0
            record = make_trial_record(
                trial_id=step.trial.trial_id,
                experiment_id=step.trial.experiment_id,
                task_id=step.trial.task_id,
                agent={
                    "adapter": "direct",
                    "model": "fixed",
                    "adapter_revision": "test",
                    "configuration": {},
                },
                environment={
                    "runtime_image": "local",
                    "compute_backend": "local",
                    "tool_versions": {},
                },
                evaluation={
                    "reward": reward,
                    "validity": {
                        "output_parseable": True,
                        "schema_valid": True,
                        "verifier_completed": True,
                    },
                },
            )
            records.append(record)
            steps.append(
                StepExecutionResult(
                    step_id=step.step_id,
                    step_index=index,
                    kind="run_experience",
                    status=StepExecutionStatus.COMPLETED,
                    state_before_id=f"{arm_run.arm_run_id}:state:{index:03d}",
                    candidate_state_id=f"{arm_run.arm_run_id}:state:{index + 1:03d}",
                    committed_state_id=f"{arm_run.arm_run_id}:state:{index:03d}"
                    if step.experience_id == "probe"
                    else f"{arm_run.arm_run_id}:state:{index + 1:03d}",
                    state_committed=step.experience_id != "probe",
                    trial_record=record,
                )
            )
        arm_results.append(
            ArmRunExecutionResult(
                arm_run_id=arm_run.arm_run_id,
                status=ArmRunStatus.COMPLETED,
                initial_state_id=f"{arm_run.arm_run_id}:state:000",
                completed_steps=tuple(steps),
                trial_records=tuple(records),
                final_state_id=steps[-1].committed_state_id,
                failure=None,
            )
        )
    return LearningStudyExecution(study_run_id=plan.study_run_id, arm_runs=tuple(arm_results))


def _evidence(
    plan: CompiledLearningStudy,
    *,
    isolated: bool = True,
    equivalent: bool = True,
    family_reviewed: bool = True,
) -> dict[str, AssessmentArmEvidence]:
    result = {}
    for arm_run in plan.arm_runs:
        equivalence = f"initial-r{arm_run.repetition}" if equivalent or arm_run.arm_id == "cold" else "different"
        result[arm_run.arm_run_id] = AssessmentArmEvidence(
            arm_run_id=arm_run.arm_run_id,
            adapter_id="artifact-local",
            initial_state_equivalence_id=equivalence,
            arm_isolated=isolated,
            family_reviewed=family_reviewed,
        )
    return result


def _reward_projection(record: TrialRecord) -> ProjectionResult:
    evaluation = record.evaluation
    if evaluation is None or evaluation.reward is None:
        return ProjectionResult(eligible=False, value=None, reason="reward unavailable")
    return ProjectionResult(eligible=True, value=float(evaluation.reward), lower_bound=0.0, upper_bound=1.0)


def test_assessment_retains_controlled_pairs_and_absolute_values() -> None:
    plan = _plan()
    execution = _execution(
        plan,
        {
            ("cold", 1): 0.2,
            ("exposed", 1): 0.7,
            ("cold", 2): 0.4,
            ("exposed", 2): 0.3,
        },
    )

    result = assess_learning_study(
        spec=plan.spec,
        plan=plan,
        execution=execution,
        projections={"task-outcome": _reward_projection},
        arm_evidence=_evidence(plan),
    ).measurements[0]

    assert result.validity is LearningComparisonValidity.CONTROLLED
    assert [pair.normalised_effect for pair in result.included_pairs] == pytest.approx([0.5, -0.1])
    assert result.focal_mean == pytest.approx(0.5)
    assert result.comparator_mean == pytest.approx(0.3)
    assert result.mean_effect == pytest.approx(0.2)
    assert result.effect_range == pytest.approx((-0.1, 0.5))


@pytest.mark.parametrize(
    ("evidence", "expected", "diagnostic"),
    [
        ({"isolated": False}, LearningComparisonValidity.INVALID, "arm isolation failed"),
        ({"equivalent": False}, LearningComparisonValidity.DESCRIPTIVE_ONLY, "not independently equivalent"),
        ({"family_reviewed": False}, LearningComparisonValidity.DESCRIPTIVE_ONLY, "not reviewed"),
    ],
)
def test_assessment_downgrades_or_invalidates_control_failures(
    evidence: dict[str, bool],
    expected: LearningComparisonValidity,
    diagnostic: str,
) -> None:
    plan = _plan(repetitions=1)
    execution = _execution(plan, {("cold", 1): 0.2, ("exposed", 1): 0.7})

    result = assess_learning_study(
        spec=plan.spec,
        plan=plan,
        execution=execution,
        projections={"task-outcome": _reward_projection},
        arm_evidence=_evidence(plan, **evidence),
    ).measurements[0]

    assert result.validity is expected
    assert len(result.included_pairs) == 1
    assert any(diagnostic in item for item in result.diagnostics)


def test_assessment_excludes_ineligible_pairs_without_rematching() -> None:
    plan = _plan()
    execution = _execution(
        plan,
        {("cold", 1): 0.2, ("exposed", 1): 0.7, ("cold", 2): 0.4, ("exposed", 2): 0.3},
    )

    def exclude_one(record: TrialRecord) -> ProjectionResult:
        projected = _reward_projection(record)
        if projected.value == 0.4:
            return ProjectionResult(eligible=False, value=None, reason="task-owned outcome unavailable")
        return projected

    result = assess_learning_study(
        spec=plan.spec,
        plan=plan,
        execution=execution,
        projections={"task-outcome": exclude_one},
        arm_evidence=_evidence(plan),
    ).measurements[0]

    assert [pair.repetition for pair in result.included_pairs] == [1]
    assert result.excluded_repetitions[0].repetition == 2
    assert "task-owned outcome unavailable" in result.excluded_repetitions[0].reasons[0]


def test_assessment_honours_lower_is_better_and_has_deterministic_bootstrap() -> None:
    plan = _plan(repetitions=5, direction=ImprovementDirection.LOWER)
    rewards = {
        (arm_id, repetition): value for repetition in range(1, 6) for arm_id, value in (("cold", 0.6), ("exposed", 0.4))
    }
    execution = _execution(plan, rewards)

    first = assess_learning_study(
        spec=plan.spec,
        plan=plan,
        execution=execution,
        projections={"task-outcome": _reward_projection},
        arm_evidence=_evidence(plan),
    ).measurements[0]
    second = assess_learning_study(
        spec=plan.spec,
        plan=plan,
        execution=execution,
        projections={"task-outcome": _reward_projection},
        arm_evidence=_evidence(plan),
    ).measurements[0]

    assert first.mean_effect == pytest.approx(0.2)
    assert first.confidence_interval_95 == pytest.approx((0.2, 0.2))
    assert first.confidence_interval_95 == second.confidence_interval_95
