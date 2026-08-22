# ABOUTME: Defines the A01 single-room heat-load structural-transfer protocol.
# ABOUTME: Uses a cold probe and an exposed probe without encoding an expected effect direction.

from __future__ import annotations

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import (
    ConsolidateStep,
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
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.assessment import ProjectionResult

A01_FAMILY_SPEC_PATH = "docs/examples/learning-studies/families/heat-load-single-room.toml"
A01_FAMILY_RELATION_ID = "brisbane-office-to-sydney-classroom"
A01_ACQUISITION_TASK_ID = "mechanical/heat-load/single-room-office-L3/brisbane-office-85m2"
A01_PROBE_TASK_ID = "mechanical/heat-load/single-room-office-L3/sydney-classroom-120m2"
A01_PROJECTION_ID = "heat-load-verifier-reward"
A01_FEEDBACK_VIEW_ID = "heat-load-public-evaluation"
A01_CONSOLIDATION_OPERATION_ID = "update-structured-memory"


def build_a01_study_spec(
    *,
    agent: AgentConfig,
    compute: ComputeConfig,
    repetitions: int = 1,
) -> LearningStudySpec:
    """Build the frozen Stage 1 A01 protocol for cold and structured-memory arms."""

    return LearningStudySpec(
        study_id="a01-artifact-structural-transfer",
        title="Artifact structural transfer: single-room cooling load",
        research_question=(
            "Does public feedback and explicit structured memory from the Brisbane office calculation change "
            "performance on the matched Sydney classroom calculation?"
        ),
        claim_mode=StudyClaimMode.CONTROLLED,
        agent=agent,
        compute=compute,
        repetitions=repetitions,
        experiences=(
            LearningExperienceSpec(
                experience_id="brisbane-office-acquisition",
                task_id=A01_ACQUISITION_TASK_ID,
                role=ExperienceRole.ACQUISITION,
            ),
            LearningExperienceSpec(
                experience_id="sydney-classroom-probe",
                task_id=A01_PROBE_TASK_ID,
                role=ExperienceRole.PROBE,
            ),
        ),
        relations=(
            ExperienceRelationSpec(
                relation_id=A01_FAMILY_RELATION_ID,
                purpose=ExperienceRelationPurpose.TRANSFER,
                source_experience_ids=("brisbane-office-acquisition",),
                target_experience_id="sydney-classroom-probe",
                invariant_claims=(
                    "Both tasks use the same AS 1668.2 lookup and psychrometric heat-load summation procedure.",
                    "Both task verifiers score the same twelve named output quantities.",
                ),
                changed_dimensions=("room_program", "climate_and_loads"),
                rationale=(
                    "The probe changes room use, standards values, climate, floor area, and internal loads while "
                    "retaining the calculation sequence."
                ),
            ),
        ),
        measurements=(
            LearningMeasurementSpec(
                measurement_id="structured-memory-transfer-gain",
                kind=LearningMeasurementKind.TRANSFER_GAIN,
                projection_id=A01_PROJECTION_ID,
                direction=ImprovementDirection.HIGHER,
                target_experience_id="sydney-classroom-probe",
                focal_arm_id="structured-memory",
                comparator_arm_id="cold-reset",
                acquisition_experience_ids=("brisbane-office-acquisition",),
            ),
        ),
        arms=(
            LearningArmSpec(
                arm_id="cold-reset",
                role=StudyArmRole.CONTROL,
                treatment_id="reset",
                steps=(
                    RunExperienceStep(
                        step_id="cold-probe",
                        experience_id="sydney-classroom-probe",
                        commit_post_state=False,
                    ),
                ),
            ),
            LearningArmSpec(
                arm_id="structured-memory",
                role=StudyArmRole.EXPOSURE,
                treatment_id="structured-memory",
                steps=(
                    RunExperienceStep(
                        step_id="acquisition",
                        experience_id="brisbane-office-acquisition",
                        commit_post_state=True,
                    ),
                    ReleaseFeedbackStep(
                        step_id="release-acquisition-feedback",
                        source_experience_id="brisbane-office-acquisition",
                        feedback_view_id=A01_FEEDBACK_VIEW_ID,
                    ),
                    ConsolidateStep(
                        step_id="consolidate-method",
                        feedback_step_ids=("release-acquisition-feedback",),
                        operation_id=A01_CONSOLIDATION_OPERATION_ID,
                    ),
                    RunExperienceStep(
                        step_id="exposed-probe",
                        experience_id="sydney-classroom-probe",
                        commit_post_state=False,
                    ),
                ),
            ),
        ),
    )


def project_heat_load_verifier_reward(record: TrialRecord) -> ProjectionResult:
    """Project the heat-load task verifier's canonical reward without parsing its breakdown."""

    if record.evaluation is None:
        return ProjectionResult(eligible=False, value=None, reason="task evaluation is unavailable")
    return ProjectionResult(
        eligible=True,
        value=record.evaluation.reward,
        lower_bound=0.0,
        upper_bound=1.0,
    )


__all__ = (
    "A01_ACQUISITION_TASK_ID",
    "A01_CONSOLIDATION_OPERATION_ID",
    "A01_FAMILY_RELATION_ID",
    "A01_FAMILY_SPEC_PATH",
    "A01_FEEDBACK_VIEW_ID",
    "A01_PROBE_TASK_ID",
    "A01_PROJECTION_ID",
    "build_a01_study_spec",
    "project_heat_load_verifier_reward",
)
