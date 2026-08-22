# ABOUTME: Tests deterministic Learning Study compilation into ordinary planned trials.
# ABOUTME: Rejects unresolved references and invalid controlled-probe ordering before execution.

from __future__ import annotations

from dataclasses import dataclass

import pytest

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import (
    ExperienceRelationPurpose,
    ExperienceRelationSpec,
    ExperienceRole,
    ImprovementDirection,
    LearningArmSpec,
    LearningExperienceSpec,
    LearningMeasurementKind,
    LearningMeasurementSpec,
    LearningStudySpec,
    ReleaseFeedbackStep,
    RunExperienceStep,
    StudyArmRole,
    StudyClaimMode,
)
from aec_bench.experimentation.learning_studies.errors import (
    LearningStudyOrderInvalid,
    LearningStudyReferenceInvalid,
    LearningStudySpecInvalid,
    LearningStudyTaskResolutionFailed,
)
from aec_bench.experimentation.learning_studies.planning import (
    CompiledExperienceStep,
    compile_learning_study,
    compiled_learning_study_to_data,
)


@dataclass(frozen=True)
class _Task:
    task_id: str


def _spec(*, probe_commit: bool | None = None, repetitions: int = 2) -> LearningStudySpec:
    return LearningStudySpec(
        study_id="study",
        title="Study",
        research_question="Question?",
        claim_mode=StudyClaimMode.CONTROLLED,
        agent=AgentConfig(name="agent", adapter="direct", model="fixed"),
        compute=ComputeConfig(backend="local"),
        repetitions=repetitions,
        experiences=(
            LearningExperienceSpec(experience_id="acquire", task_id="task/acquire", role=ExperienceRole.ACQUISITION),
            LearningExperienceSpec(experience_id="probe", task_id="task/probe", role=ExperienceRole.PROBE),
        ),
        arms=(
            LearningArmSpec(
                arm_id="cold",
                role=StudyArmRole.CONTROL,
                treatment_id="reset",
                steps=(RunExperienceStep(step_id="probe", experience_id="probe", commit_post_state=probe_commit),),
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
                    RunExperienceStep(
                        step_id="probe",
                        experience_id="probe",
                        commit_post_state=probe_commit,
                    ),
                ),
            ),
        ),
    )


def test_compilation_is_deterministic_interleaved_and_uses_ordinary_trials() -> None:
    resolver = lambda task_id: _Task(task_id)  # noqa: E731

    first = compile_learning_study(study_run_id="run-1", spec=_spec(), resolve_task=resolver)
    second = compile_learning_study(study_run_id="run-1", spec=_spec(), resolve_task=resolver)

    assert compiled_learning_study_to_data(first) == compiled_learning_study_to_data(second)
    assert [(item.repetition, item.arm_id) for item in first.arm_runs] == [
        (1, "cold"),
        (1, "exposed"),
        (2, "cold"),
        (2, "exposed"),
    ]
    trial_ids = [
        step.trial.trial_id
        for arm_run in first.arm_runs
        for step in arm_run.steps
        if isinstance(step, CompiledExperienceStep)
    ]
    assert len(trial_ids) == len(set(trial_ids)) == 6
    probes = [
        step
        for arm_run in first.arm_runs
        for step in arm_run.steps
        if isinstance(step, CompiledExperienceStep) and step.role is ExperienceRole.PROBE
    ]
    assert probes and all(not step.commit_post_state for step in probes)


def test_compilation_resolves_every_task_before_execution() -> None:
    def resolve(task_id: str) -> _Task:
        if task_id == "task/probe":
            raise FileNotFoundError("not found")
        return _Task(task_id)

    with pytest.raises(LearningStudyTaskResolutionFailed, match="experience probe"):
        compile_learning_study(study_run_id="run-1", spec=_spec(), resolve_task=resolve)


def test_compilation_preserves_family_specific_changed_dimension_ids() -> None:
    relation = ExperienceRelationSpec(
        relation_id="boundary",
        purpose=ExperienceRelationPurpose.BOUNDARY,
        source_experience_ids=("acquire",),
        target_experience_id="probe",
        invariant_claims=("The review workflow stays fixed.",),
        changed_dimensions=("issue_locus", "transition_scope"),
        rationale="The family overlay declares the semantic kinds of these dimensions.",
    )

    compiled = compile_learning_study(
        study_run_id="run-1",
        spec=_spec().model_copy(update={"relations": (relation,)}),
        resolve_task=lambda task_id: _Task(task_id),
    )

    assert compiled.spec.relations == (relation,)


def test_compilation_accepts_retention_decay_between_two_probes_in_one_exposed_arm() -> None:
    spec = _spec(repetitions=1)
    delayed = LearningExperienceSpec(experience_id="delayed", task_id="task/delayed", role=ExperienceRole.PROBE)
    cold = spec.arms[0].model_copy(update={"steps": (RunExperienceStep(step_id="delayed", experience_id="delayed"),)})
    exposed = spec.arms[1].model_copy(
        update={"steps": (*spec.arms[1].steps, RunExperienceStep(step_id="delayed", experience_id="delayed"))}
    )
    measurement = LearningMeasurementSpec(
        measurement_id="decay",
        kind=LearningMeasurementKind.RETENTION_DECAY,
        projection_id="reward",
        direction=ImprovementDirection.LOWER,
        target_experience_id="delayed",
        focal_arm_id="exposed",
        reference_experience_id="probe",
        acquisition_experience_ids=("acquire",),
    )

    compiled = compile_learning_study(
        study_run_id="run-1",
        spec=spec.model_copy(
            update={
                "experiences": (*spec.experiences, delayed),
                "arms": (cold, exposed),
                "measurements": (measurement,),
            }
        ),
        resolve_task=lambda task_id: _Task(task_id),
    )

    assert compiled.spec.measurements == (measurement,)


def test_compilation_rejects_ambiguous_or_unexecuted_retention_references() -> None:
    spec = _spec(repetitions=1)
    base = LearningMeasurementSpec(
        measurement_id="decay",
        kind=LearningMeasurementKind.RETENTION_DECAY,
        projection_id="reward",
        direction=ImprovementDirection.LOWER,
        target_experience_id="probe",
        focal_arm_id="exposed",
        reference_experience_id="acquire",
    )
    with pytest.raises(LearningStudySpecInvalid, match="cannot use both"):
        compile_learning_study(
            study_run_id="run-1",
            spec=spec.model_copy(update={"measurements": (base.model_copy(update={"comparator_arm_id": "cold"}),)}),
            resolve_task=lambda task_id: _Task(task_id),
        )

    with pytest.raises(LearningStudyReferenceInvalid, match="does not run reference experience"):
        compile_learning_study(
            study_run_id="run-1",
            spec=spec.model_copy(
                update={
                    "measurements": (
                        base.model_copy(update={"focal_arm_id": "cold", "reference_experience_id": "acquire"}),
                    )
                }
            ),
            resolve_task=lambda task_id: _Task(task_id),
        )

    with pytest.raises(LearningStudySpecInvalid, match="requires a reference experience"):
        compile_learning_study(
            study_run_id="run-1",
            spec=spec.model_copy(update={"measurements": (base.model_copy(update={"reference_experience_id": None}),)}),
            resolve_task=lambda task_id: _Task(task_id),
        )


def test_compilation_rejects_feedback_before_source_and_probe_commit() -> None:
    spec = _spec()
    exposure = spec.arms[1].model_copy(
        update={
            "steps": (
                spec.arms[1].steps[1],
                spec.arms[1].steps[0],
                spec.arms[1].steps[2],
            )
        }
    )
    invalid_order = spec.model_copy(update={"arms": (spec.arms[0], exposure)})

    with pytest.raises(LearningStudyOrderInvalid, match="feedback source has not run"):
        compile_learning_study(
            study_run_id="run-1",
            spec=invalid_order,
            resolve_task=lambda task_id: _Task(task_id),
        )
    with pytest.raises(LearningStudyOrderInvalid, match="controlled probe cannot commit"):
        compile_learning_study(
            study_run_id="run-1",
            spec=_spec(probe_commit=True),
            resolve_task=lambda task_id: _Task(task_id),
        )


def test_compilation_rejects_undeclared_experience_reference() -> None:
    spec = _spec()
    invalid_arm = spec.arms[0].model_copy(
        update={"steps": (RunExperienceStep(step_id="probe", experience_id="missing"),)}
    )

    with pytest.raises(LearningStudyReferenceInvalid, match="unknown experience missing"):
        compile_learning_study(
            study_run_id="run-1",
            spec=spec.model_copy(update={"arms": (invalid_arm, spec.arms[1])}),
            resolve_task=lambda task_id: _Task(task_id),
        )


def test_compilation_rejects_repeated_experience_in_one_arm() -> None:
    spec = _spec()
    exposure = spec.arms[1].model_copy(
        update={"steps": (*spec.arms[1].steps, RunExperienceStep(step_id="probe-again", experience_id="probe"))}
    )

    with pytest.raises(LearningStudyOrderInvalid, match="experience probe already ran"):
        compile_learning_study(
            study_run_id="run-1",
            spec=spec.model_copy(update={"arms": (spec.arms[0], exposure)}),
            resolve_task=lambda task_id: _Task(task_id),
        )


def test_compilation_error_identifies_study_and_arm_for_unsafe_step_id() -> None:
    spec = _spec()
    invalid_cold = spec.arms[0].model_copy(
        update={"steps": (RunExperienceStep(step_id="unsafe/step", experience_id="probe"),)}
    )

    with pytest.raises(LearningStudySpecInvalid, match="study study arm cold: step id"):
        compile_learning_study(
            study_run_id="run-1",
            spec=spec.model_copy(update={"arms": (invalid_cold, spec.arms[1])}),
            resolve_task=lambda task_id: _Task(task_id),
        )
