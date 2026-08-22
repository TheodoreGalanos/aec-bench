# ABOUTME: Tests strict authored Learning Study contracts and planned-trial persistence.
# ABOUTME: Proves the study language remains finite, explicit, and round-trippable.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import (
    ConsolidateStep,
    ExperienceRelationPurpose,
    ExperienceRelationSpec,
    ExperienceRole,
    LearningArmSpec,
    LearningExperienceSpec,
    LearningStudySpec,
    ReleaseFeedbackStep,
    RunExperienceStep,
    StudyArmRole,
)
from aec_bench.contracts.validators import StrictModel
from aec_bench.trials import PlannedTrial, planned_trial_from_data, planned_trial_to_data


class _TrialExtension(StrictModel):
    value: str


def _spec() -> LearningStudySpec:
    return LearningStudySpec(
        study_id="method-transfer",
        title="Method transfer",
        research_question="Does the method transfer?",
        agent=AgentConfig(name="learner", adapter="direct", model="fixed-model"),
        compute=ComputeConfig(backend="local", timeout_override=30),
        repetitions=2,
        experiences=(
            LearningExperienceSpec(experience_id="acquire", task_id="tasks/acquire", role=ExperienceRole.ACQUISITION),
            LearningExperienceSpec(experience_id="probe", task_id="tasks/probe", role=ExperienceRole.PROBE),
        ),
        relations=(
            ExperienceRelationSpec(
                relation_id="same-method",
                purpose=ExperienceRelationPurpose.TRANSFER,
                source_experience_ids=("acquire",),
                target_experience_id="probe",
                invariant_claims=("The governing method is unchanged.",),
                changed_dimensions=("surface",),
                rationale="Tests transfer across a changed surface.",
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
                arm_id="memory",
                role=StudyArmRole.EXPOSURE,
                treatment_id="structured-memory",
                steps=(
                    RunExperienceStep(step_id="acquire-task", experience_id="acquire"),
                    ReleaseFeedbackStep(
                        step_id="acquire-feedback",
                        source_experience_id="acquire",
                        feedback_view_id="public-evaluation",
                    ),
                    ConsolidateStep(
                        step_id="consolidate",
                        feedback_step_ids=("acquire-feedback",),
                        operation_id="update-memory",
                    ),
                    RunExperienceStep(step_id="transfer-probe", experience_id="probe"),
                ),
            ),
        ),
    )


def test_learning_study_contract_round_trips_strictly() -> None:
    spec = _spec()

    loaded = LearningStudySpec.model_validate_json(spec.model_dump_json())

    assert loaded == spec
    with pytest.raises(ValidationError, match="Extra inputs"):
        LearningStudySpec.model_validate({**spec.model_dump(mode="python"), "workflow": {}})


def test_learning_study_contract_rejects_duplicate_and_unknown_steps() -> None:
    arm = _spec().arms[0]

    with pytest.raises(ValidationError, match="step ids must be unique"):
        LearningArmSpec(
            arm_id=arm.arm_id,
            role=arm.role,
            treatment_id=arm.treatment_id,
            steps=(arm.steps[0], arm.steps[0]),
        )
    payload = arm.model_dump(mode="python")
    payload["steps"] = ({"kind": "branch", "step_id": "branch-1"},)
    with pytest.raises(ValidationError, match="union_tag_invalid"):
        LearningArmSpec.model_validate(payload)


def test_planned_trial_round_trip_requires_explicit_extension_types() -> None:
    trial = PlannedTrial(
        trial_id="trial-1",
        experiment_id="experiment-1",
        task_id="tasks/probe",
        agent=_spec().agent,
        compute=_spec().compute,
        repetition=1,
        extensions={"example": _TrialExtension(value="kept")},
    )
    data = planned_trial_to_data(trial)

    with pytest.raises(ValueError, match="extension types are required"):
        planned_trial_from_data(data)

    loaded = planned_trial_from_data(data, extension_types={"example": _TrialExtension})

    assert planned_trial_to_data(loaded) == data
