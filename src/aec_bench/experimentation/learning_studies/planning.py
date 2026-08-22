# ABOUTME: Compiles finite Learning Study specifications into exact ordinary planned trials.
# ABOUTME: Resolves every task and step before execution without adding another trial model.

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from aec_bench.contracts.learning_study import (
    ConsolidateStep,
    ExperienceRole,
    LearningMeasurementKind,
    LearningStudySpec,
    ReleaseFeedbackStep,
    RunExperienceStep,
    StudyArmRole,
    StudyClaimMode,
)
from aec_bench.experimentation.learning_studies.errors import (
    LearningStudyOrderInvalid,
    LearningStudyPlanCollision,
    LearningStudyReferenceInvalid,
    LearningStudySpecInvalid,
    LearningStudyTaskResolutionFailed,
)
from aec_bench.trials import PlannableTask, PlannedTrial, build_trial_id, planned_trial_to_data

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


@dataclass(frozen=True)
class CompiledExperienceStep:
    step_id: str
    experience_id: str
    role: ExperienceRole
    trial: PlannedTrial
    commit_post_state: bool


@dataclass(frozen=True)
class CompiledFeedbackStep:
    step_id: str
    source_experience_id: str
    feedback_view_id: str


@dataclass(frozen=True)
class CompiledConsolidationStep:
    step_id: str
    feedback_step_ids: tuple[str, ...]
    operation_id: str


type CompiledStudyStep = CompiledExperienceStep | CompiledFeedbackStep | CompiledConsolidationStep


@dataclass(frozen=True)
class PlannedArmRun:
    arm_run_id: str
    arm_id: str
    arm_role: StudyArmRole
    treatment_id: str
    repetition: int
    steps: tuple[CompiledStudyStep, ...]


@dataclass(frozen=True)
class CompiledLearningStudy:
    study_run_id: str
    spec: LearningStudySpec
    arm_runs: tuple[PlannedArmRun, ...]


def compile_learning_study(
    *,
    study_run_id: str,
    spec: LearningStudySpec,
    resolve_task: Callable[[str], PlannableTask],
) -> CompiledLearningStudy:
    """Resolve one complete finite study before any execution starts."""

    _validate_safe_id("study run", study_run_id, context=f"study {spec.study_id}")
    _validate_references(spec)
    _validate_measurements(spec)
    _validate_controlled_shape(spec)
    resolved: dict[str, PlannableTask] = {}
    for experience in spec.experiences:
        try:
            task = resolve_task(experience.task_id)
        except Exception as error:
            raise LearningStudyTaskResolutionFailed(
                f"study {spec.study_id} experience {experience.experience_id} could not resolve task "
                f"{experience.task_id}: {error}"
            ) from error
        if task.task_id != experience.task_id:
            raise LearningStudyTaskResolutionFailed(
                f"study {spec.study_id} experience {experience.experience_id} resolved task {task.task_id}, "
                f"expected {experience.task_id}"
            )
        resolved[experience.experience_id] = task

    experiences = {item.experience_id: item for item in spec.experiences}
    arm_runs: list[PlannedArmRun] = []
    trial_ids: set[str] = set()
    arm_run_ids: set[str] = set()
    for repetition in range(1, spec.repetitions + 1):
        for arm in spec.arms:
            arm_run_id = f"{study_run_id}--{arm.arm_id}--r{repetition:02d}"
            if arm_run_id in arm_run_ids:
                raise LearningStudyPlanCollision(f"duplicate arm run id: {arm_run_id}")
            arm_run_ids.add(arm_run_id)
            compiled_steps: list[CompiledStudyStep] = []
            for step in arm.steps:
                if isinstance(step, RunExperienceStep):
                    experience = experiences[step.experience_id]
                    experiment_id = f"{study_run_id}--{arm.arm_id}--{step.step_id}"
                    trial_id = build_trial_id(
                        experiment_id=experiment_id,
                        task_id=experience.task_id,
                        agent_name=spec.agent.name,
                        repetition=repetition,
                    )
                    if trial_id in trial_ids:
                        raise LearningStudyPlanCollision(f"duplicate planned trial id: {trial_id}")
                    trial_ids.add(trial_id)
                    commit_post_state = (
                        step.commit_post_state
                        if step.commit_post_state is not None
                        else experience.role is not ExperienceRole.PROBE
                    )
                    if (
                        spec.claim_mode is StudyClaimMode.CONTROLLED
                        and experience.role is ExperienceRole.PROBE
                        and commit_post_state
                    ):
                        raise LearningStudyOrderInvalid(
                            f"study {spec.study_id} arm {arm.arm_id} step {step.step_id}: "
                            "a controlled probe cannot commit post-state"
                        )
                    compiled_steps.append(
                        CompiledExperienceStep(
                            step_id=step.step_id,
                            experience_id=step.experience_id,
                            role=experience.role,
                            trial=PlannedTrial(
                                trial_id=trial_id,
                                experiment_id=experiment_id,
                                task_id=experience.task_id,
                                agent=spec.agent,
                                compute=spec.compute,
                                repetition=repetition,
                            ),
                            commit_post_state=commit_post_state,
                        )
                    )
                elif isinstance(step, ReleaseFeedbackStep):
                    compiled_steps.append(
                        CompiledFeedbackStep(
                            step_id=step.step_id,
                            source_experience_id=step.source_experience_id,
                            feedback_view_id=step.feedback_view_id,
                        )
                    )
                elif isinstance(step, ConsolidateStep):
                    compiled_steps.append(
                        CompiledConsolidationStep(
                            step_id=step.step_id,
                            feedback_step_ids=step.feedback_step_ids,
                            operation_id=step.operation_id,
                        )
                    )
                else:  # pragma: no cover - Pydantic rejects unknown discriminators.
                    raise TypeError(f"unsupported learning study step: {type(step).__name__}")
            arm_runs.append(
                PlannedArmRun(
                    arm_run_id=arm_run_id,
                    arm_id=arm.arm_id,
                    arm_role=arm.role,
                    treatment_id=arm.treatment_id,
                    repetition=repetition,
                    steps=tuple(compiled_steps),
                )
            )
    return CompiledLearningStudy(study_run_id=study_run_id, spec=spec, arm_runs=tuple(arm_runs))


def compiled_learning_study_to_data(plan: CompiledLearningStudy) -> dict[str, object]:
    """Return canonical plan data for immutable persistence and exact resume checks."""

    return {
        "study_run_id": plan.study_run_id,
        "spec": plan.spec.model_dump(mode="json", round_trip=True),
        "arm_runs": [
            {
                "arm_run_id": arm_run.arm_run_id,
                "arm_id": arm_run.arm_id,
                "arm_role": arm_run.arm_role.value,
                "treatment_id": arm_run.treatment_id,
                "repetition": arm_run.repetition,
                "steps": [_compiled_step_to_data(step) for step in arm_run.steps],
            }
            for arm_run in plan.arm_runs
        ],
    }


def _compiled_step_to_data(step: CompiledStudyStep) -> dict[str, object]:
    if isinstance(step, CompiledExperienceStep):
        return {
            "kind": "run_experience",
            "step_id": step.step_id,
            "experience_id": step.experience_id,
            "role": step.role.value,
            "trial": planned_trial_to_data(step.trial),
            "commit_post_state": step.commit_post_state,
        }
    if isinstance(step, CompiledFeedbackStep):
        return {
            "kind": "release_feedback",
            "step_id": step.step_id,
            "source_experience_id": step.source_experience_id,
            "feedback_view_id": step.feedback_view_id,
        }
    return {
        "kind": "consolidate",
        "step_id": step.step_id,
        "feedback_step_ids": list(step.feedback_step_ids),
        "operation_id": step.operation_id,
    }


def _validate_references(spec: LearningStudySpec) -> None:
    experiences = {item.experience_id: item for item in spec.experiences}
    for identity in (
        spec.study_id,
        *(item.experience_id for item in spec.experiences),
        *(item.arm_id for item in spec.arms),
    ):
        _validate_safe_id("study", identity, context=f"study {spec.study_id}")
    for relation in spec.relations:
        missing = {*relation.source_experience_ids, relation.target_experience_id} - set(experiences)
        if missing:
            raise LearningStudyReferenceInvalid(
                f"study {spec.study_id} relation {relation.relation_id} references unknown experiences: "
                f"{sorted(missing)}"
            )
        target = experiences[relation.target_experience_id]
        if target.role is not ExperienceRole.PROBE:
            raise LearningStudyReferenceInvalid(
                f"study {spec.study_id} relation {relation.relation_id} target must be a probe"
            )
    for arm in spec.arms:
        seen_experiences: set[str] = set()
        seen_feedback: set[str] = set()
        released_views: set[tuple[str, str]] = set()
        for step in arm.steps:
            _validate_safe_id("step", step.step_id, context=f"study {spec.study_id} arm {arm.arm_id}")
            if isinstance(step, RunExperienceStep):
                if step.experience_id not in experiences:
                    raise LearningStudyReferenceInvalid(
                        f"study {spec.study_id} arm {arm.arm_id} step {step.step_id} references unknown experience "
                        f"{step.experience_id}"
                    )
                if step.experience_id in seen_experiences:
                    raise LearningStudyOrderInvalid(
                        f"study {spec.study_id} arm {arm.arm_id} step {step.step_id}: "
                        f"experience {step.experience_id} already ran in this arm"
                    )
                seen_experiences.add(step.experience_id)
            elif isinstance(step, ReleaseFeedbackStep):
                source = experiences.get(step.source_experience_id)
                if source is None:
                    raise LearningStudyReferenceInvalid(
                        f"study {spec.study_id} arm {arm.arm_id} step {step.step_id} references unknown experience "
                        f"{step.source_experience_id}"
                    )
                if step.source_experience_id not in seen_experiences:
                    raise LearningStudyOrderInvalid(
                        f"study {spec.study_id} arm {arm.arm_id} step {step.step_id}: feedback source has not run"
                    )
                if source.role is ExperienceRole.PROBE:
                    raise LearningStudyOrderInvalid(
                        f"study {spec.study_id} arm {arm.arm_id} step {step.step_id}: probe feedback cannot be released"
                    )
                release_key = (step.source_experience_id, step.feedback_view_id)
                if release_key in released_views:
                    raise LearningStudyOrderInvalid(
                        f"study {spec.study_id} arm {arm.arm_id} step {step.step_id}: "
                        "feedback view was already released"
                    )
                released_views.add(release_key)
                seen_feedback.add(step.step_id)
            elif isinstance(step, ConsolidateStep):
                missing_feedback = set(step.feedback_step_ids) - seen_feedback
                if missing_feedback:
                    raise LearningStudyOrderInvalid(
                        f"study {spec.study_id} arm {arm.arm_id} step {step.step_id}: "
                        "feedback steps are not available: "
                        f"{sorted(missing_feedback)}"
                    )


def _validate_controlled_shape(spec: LearningStudySpec) -> None:
    if spec.claim_mode is not StudyClaimMode.CONTROLLED:
        return
    roles = {arm.role for arm in spec.arms}
    if not {StudyArmRole.CONTROL, StudyArmRole.EXPOSURE}.issubset(roles):
        raise LearningStudySpecInvalid(
            f"study {spec.study_id}: controlled learning study requires control and exposure arms"
        )
    arm_probe_ids: dict[StudyArmRole, set[str]] = {StudyArmRole.CONTROL: set(), StudyArmRole.EXPOSURE: set()}
    experience_roles = {item.experience_id: item.role for item in spec.experiences}
    for arm in spec.arms:
        arm_probe_ids[arm.role].update(
            step.experience_id
            for step in arm.steps
            if isinstance(step, RunExperienceStep) and experience_roles.get(step.experience_id) is ExperienceRole.PROBE
        )
    if not arm_probe_ids[StudyArmRole.CONTROL].intersection(arm_probe_ids[StudyArmRole.EXPOSURE]):
        raise LearningStudySpecInvalid(
            f"study {spec.study_id}: controlled learning study requires a matched probe in control and exposure arms"
        )


def _validate_measurements(spec: LearningStudySpec) -> None:
    experiences = {item.experience_id: item for item in spec.experiences}
    arms = {item.arm_id: item for item in spec.arms}
    between_arm_kinds = {
        LearningMeasurementKind.TRANSFER_GAIN,
        LearningMeasurementKind.BOUNDARY_GAIN,
        LearningMeasurementKind.COMPOSITION_GAIN,
        LearningMeasurementKind.RETAINED_GAIN,
        LearningMeasurementKind.INTERFERENCE_EFFECT,
    }
    for measurement in spec.measurements:
        _validate_safe_id("measurement", measurement.measurement_id, context=f"study {spec.study_id}")
        target = experiences.get(measurement.target_experience_id)
        if target is None or target.role is not ExperienceRole.PROBE:
            raise LearningStudyReferenceInvalid(
                f"study {spec.study_id} measurement {measurement.measurement_id} target must be a declared probe"
            )
        focal = arms.get(measurement.focal_arm_id)
        comparator = None if measurement.comparator_arm_id is None else arms.get(measurement.comparator_arm_id)
        if focal is None or (measurement.comparator_arm_id is not None and comparator is None):
            raise LearningStudyReferenceInvalid(
                f"study {spec.study_id} measurement {measurement.measurement_id} references an unknown arm"
            )
        if measurement.kind in between_arm_kinds and comparator is None:
            raise LearningStudySpecInvalid(
                f"study {spec.study_id} measurement {measurement.measurement_id} requires a comparator arm"
            )
        if comparator is not None and comparator.arm_id == focal.arm_id:
            raise LearningStudySpecInvalid(
                f"study {spec.study_id} measurement {measurement.measurement_id} comparator must differ from focal"
            )
        if measurement.reference_experience_id is not None and comparator is not None:
            raise LearningStudySpecInvalid(
                f"study {spec.study_id} measurement {measurement.measurement_id} cannot use both a comparator arm "
                "and a reference experience"
            )
        if measurement.kind is LearningMeasurementKind.RETENTION_DECAY and measurement.reference_experience_id is None:
            raise LearningStudySpecInvalid(
                f"study {spec.study_id} measurement {measurement.measurement_id} requires a reference experience"
            )
        for arm in (focal, comparator):
            if arm is None:
                continue
            if not any(
                isinstance(step, RunExperienceStep) and step.experience_id == measurement.target_experience_id
                for step in arm.steps
            ):
                raise LearningStudyReferenceInvalid(
                    f"study {spec.study_id} measurement {measurement.measurement_id} arm {arm.arm_id} "
                    "does not run its target probe"
                )
        referenced_experiences = {
            *measurement.acquisition_experience_ids,
            *(() if measurement.reference_experience_id is None else (measurement.reference_experience_id,)),
        }
        missing = referenced_experiences - set(experiences)
        if missing:
            raise LearningStudyReferenceInvalid(
                f"study {spec.study_id} measurement {measurement.measurement_id} references unknown experiences: "
                f"{sorted(missing)}"
            )
        focal_experience_ids = {step.experience_id for step in focal.steps if isinstance(step, RunExperienceStep)}
        if (
            measurement.reference_experience_id is not None
            and measurement.reference_experience_id not in focal_experience_ids
        ):
            raise LearningStudyReferenceInvalid(
                f"study {spec.study_id} measurement {measurement.measurement_id} focal arm does not run "
                f"reference experience {measurement.reference_experience_id}"
            )
        missing_acquisition = set(measurement.acquisition_experience_ids) - focal_experience_ids
        if missing_acquisition:
            raise LearningStudyReferenceInvalid(
                f"study {spec.study_id} measurement {measurement.measurement_id} focal arm does not run "
                f"declared acquisition experiences: {sorted(missing_acquisition)}"
            )


def _validate_safe_id(label: str, value: str, *, context: str) -> None:
    if not _SAFE_ID.fullmatch(value):
        raise LearningStudySpecInvalid(
            f"{context}: {label} id must start with an alphanumeric character and contain only letters, numbers, "
            "'.', '_', or '-': "
            f"{value!r}"
        )


__all__ = (
    "CompiledConsolidationStep",
    "CompiledExperienceStep",
    "CompiledFeedbackStep",
    "CompiledLearningStudy",
    "CompiledStudyStep",
    "PlannedArmRun",
    "compile_learning_study",
    "compiled_learning_study_to_data",
)
