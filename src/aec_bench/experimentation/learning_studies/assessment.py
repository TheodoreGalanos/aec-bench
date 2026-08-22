# ABOUTME: Assesses matched Learning Study probes through caller-owned named projections.
# ABOUTME: Downgrades uncontrolled evidence and keeps every included or excluded repetition visible.

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from aec_bench.contracts.learning_study import (
    ImprovementDirection,
    LearningMeasurementSpec,
    LearningStudySpec,
    StudyArmRole,
)
from aec_bench.contracts.learning_study_assessment import (
    ExcludedPair,
    LearningComparisonValidity,
    LearningMeasurementResult,
    LearningStudyAssessment,
    PairedMeasurementValue,
)
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.planning import (
    CompiledExperienceStep,
    CompiledLearningStudy,
    PlannedArmRun,
)
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunExecutionResult,
    LearningStudyExecution,
    StepExecutionStatus,
)


@dataclass(frozen=True)
class ProjectionResult:
    eligible: bool
    value: float | None
    reason: str | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None

    def __post_init__(self) -> None:
        if self.eligible:
            if self.value is None or not math.isfinite(self.value):
                raise ValueError("eligible outcome projection requires one finite value")
            if self.reason is not None:
                raise ValueError("eligible outcome projection cannot contain an exclusion reason")
        elif self.value is not None or not self.reason:
            raise ValueError("ineligible outcome projection requires one reason and no value")
        for bound in (self.lower_bound, self.upper_bound):
            if bound is not None and not math.isfinite(bound):
                raise ValueError("outcome projection bounds must be finite")
        if self.lower_bound is not None and self.upper_bound is not None and self.lower_bound > self.upper_bound:
            raise ValueError("outcome projection lower bound cannot exceed its upper bound")


type OutcomeProjection = Callable[[TrialRecord], ProjectionResult]


def project_trial_reward(record: TrialRecord) -> ProjectionResult:
    """Project the task evaluator's canonical reward without parsing its breakdown."""

    if record.evaluation is None:
        return ProjectionResult(eligible=False, value=None, reason="task evaluation is unavailable")
    return ProjectionResult(
        eligible=True,
        value=record.evaluation.reward,
        lower_bound=0.0,
        upper_bound=1.0,
    )


@dataclass(frozen=True)
class AssessmentArmEvidence:
    adapter_id: str
    initial_state_equivalence_id: str
    arm_isolated: bool
    lineage_complete: bool
    probe_feedback_hidden: bool
    probe_state_discarded: bool
    hidden_evaluation_leaked: bool


def assess_learning_study(
    *,
    spec: LearningStudySpec,
    plan: CompiledLearningStudy,
    execution: LearningStudyExecution[object],
    projections: Mapping[str, OutcomeProjection],
    arm_evidence: Mapping[str, AssessmentArmEvidence],
    relations_reviewed: bool,
) -> LearningStudyAssessment:
    """Return deterministic pair-level measurements without interpreting task payloads."""

    if spec != plan.spec or execution.study_run_id != plan.study_run_id:
        raise ValueError("assessment inputs do not identify the same compiled study")
    execution_by_id = {item.arm_run_id: item for item in execution.arm_runs}
    measurements = tuple(
        _assess_measurement(
            measurement=measurement,
            plan=plan,
            execution_by_id=execution_by_id,
            projection=projections.get(measurement.projection_id),
            arm_evidence=arm_evidence,
            relations_reviewed=relations_reviewed,
        )
        for measurement in spec.measurements
    )
    return LearningStudyAssessment(study_run_id=plan.study_run_id, measurements=measurements)


def _assess_measurement(
    *,
    measurement: LearningMeasurementSpec,
    plan: CompiledLearningStudy,
    execution_by_id: Mapping[str, ArmRunExecutionResult[object]],
    projection: OutcomeProjection | None,
    arm_evidence: Mapping[str, AssessmentArmEvidence],
    relations_reviewed: bool,
) -> LearningMeasurementResult:
    if projection is None:
        return _empty_result(
            measurement,
            LearningComparisonValidity.INVALID,
            (f"outcome projection is unavailable: {measurement.projection_id}",),
        )
    focal_runs = _runs_for_arm(plan, measurement.focal_arm_id)
    comparator_runs = (
        {} if measurement.comparator_arm_id is None else _runs_for_arm(plan, measurement.comparator_arm_id)
    )
    included: list[PairedMeasurementValue] = []
    excluded: list[ExcludedPair] = []
    diagnostics: set[str] = set()
    validity = LearningComparisonValidity.CONTROLLED

    for repetition in range(1, plan.spec.repetitions + 1):
        focal_plan = focal_runs.get(repetition)
        comparator_plan = comparator_runs.get(repetition)
        reasons: list[str] = []
        if focal_plan is None:
            reasons.append("focal arm run is missing from the plan")
        if measurement.comparator_arm_id is not None and comparator_plan is None:
            reasons.append("comparator arm run is missing from the plan")
        if reasons:
            excluded.append(ExcludedPair(repetition=repetition, reasons=tuple(reasons)))
            validity = LearningComparisonValidity.INVALID
            continue
        assert focal_plan is not None
        focal_execution = execution_by_id.get(focal_plan.arm_run_id)
        comparator_execution = None if comparator_plan is None else execution_by_id.get(comparator_plan.arm_run_id)
        focal_record = _experience_record(focal_plan, focal_execution, measurement.target_experience_id)
        if measurement.reference_experience_id is not None and comparator_plan is None:
            comparator_record = _experience_record(
                focal_plan,
                focal_execution,
                measurement.reference_experience_id,
            )
        else:
            comparator_record = _experience_record(
                comparator_plan,
                comparator_execution,
                measurement.target_experience_id,
            )
        if focal_record is None:
            reasons.append("focal target probe did not produce a completed TrialRecord")
        if (
            comparator_plan is not None or measurement.reference_experience_id is not None
        ) and comparator_record is None:
            reasons.append("comparator target probe did not produce a completed TrialRecord")
        if reasons:
            excluded.append(ExcludedPair(repetition=repetition, reasons=tuple(reasons)))
            validity = LearningComparisonValidity.INVALID
            continue
        assert focal_record is not None
        focal_projection = projection(focal_record)
        comparator_projection = None if comparator_record is None else projection(comparator_record)
        if not focal_projection.eligible:
            reasons.append(f"focal projection ineligible: {focal_projection.reason}")
        if comparator_projection is not None and not comparator_projection.eligible:
            reasons.append(f"comparator projection ineligible: {comparator_projection.reason}")
        if reasons:
            excluded.append(ExcludedPair(repetition=repetition, reasons=tuple(reasons)))
            continue
        assert focal_projection.value is not None
        comparator_value = None if comparator_projection is None else comparator_projection.value
        effect = _normalised_effect(
            focal=focal_projection.value,
            comparator=comparator_value,
            direction=measurement.direction,
        )
        included.append(
            PairedMeasurementValue(
                repetition=repetition,
                focal_trial_id=focal_record.trial_id,
                comparator_trial_id=None if comparator_record is None else comparator_record.trial_id,
                focal_value=focal_projection.value,
                comparator_value=comparator_value,
                normalised_effect=effect,
            )
        )
        pair_validity, pair_diagnostics = _pair_validity(
            plan=plan,
            focal_plan=focal_plan,
            comparator_plan=comparator_plan,
            focal_record=focal_record,
            comparator_record=comparator_record,
            evidence=arm_evidence,
            require_matching_task=measurement.reference_experience_id is None,
            relations_reviewed=relations_reviewed,
        )
        diagnostics.update(pair_diagnostics)
        validity = _least_valid(validity, pair_validity)
        diagnostics.update(_bound_diagnostics(focal_projection, comparator_projection))

    if not included:
        validity = LearningComparisonValidity.INVALID
        diagnostics.add("no eligible matched repetitions")
    elif measurement.comparator_arm_id is None:
        validity = _least_valid(validity, LearningComparisonValidity.DESCRIPTIVE_ONLY)
        diagnostics.add("measurement has no matched between-arm comparator")
    effects = [item.normalised_effect for item in included]
    focal_values = [item.focal_value for item in included]
    comparator_values = [item.comparator_value for item in included if item.comparator_value is not None]
    return LearningMeasurementResult(
        measurement_id=measurement.measurement_id,
        validity=validity,
        projection_id=measurement.projection_id,
        included_pairs=tuple(included),
        excluded_repetitions=tuple(excluded),
        focal_mean=_mean_or_none(focal_values),
        comparator_mean=_mean_or_none(comparator_values),
        mean_effect=_mean_or_none(effects),
        diagnostics=tuple(sorted(diagnostics)),
    )


def _runs_for_arm(plan: CompiledLearningStudy, arm_id: str) -> dict[int, PlannedArmRun]:
    return {item.repetition: item for item in plan.arm_runs if item.arm_id == arm_id}


def _experience_record(
    arm_plan: PlannedArmRun | None,
    execution: ArmRunExecutionResult[object] | None,
    experience_id: str,
) -> TrialRecord | None:
    if arm_plan is None or execution is None:
        return None
    step = next(
        (
            item
            for item in arm_plan.steps
            if isinstance(item, CompiledExperienceStep) and item.experience_id == experience_id
        ),
        None,
    )
    if step is None:
        return None
    result = next((item for item in execution.completed_steps if item.step_id == step.step_id), None)
    if result is None or result.status is not StepExecutionStatus.COMPLETED:
        return None
    return result.trial_record


def _pair_validity(
    *,
    plan: CompiledLearningStudy,
    focal_plan: PlannedArmRun,
    comparator_plan: PlannedArmRun | None,
    focal_record: TrialRecord,
    comparator_record: TrialRecord | None,
    evidence: Mapping[str, AssessmentArmEvidence],
    require_matching_task: bool,
    relations_reviewed: bool,
) -> tuple[LearningComparisonValidity, tuple[str, ...]]:
    focal_evidence = evidence.get(focal_plan.arm_run_id)
    comparator_evidence = None if comparator_plan is None else evidence.get(comparator_plan.arm_run_id)
    required = (
        ((focal_plan.arm_run_id, focal_evidence),)
        if comparator_plan is None
        else (
            (focal_plan.arm_run_id, focal_evidence),
            (comparator_plan.arm_run_id, comparator_evidence),
        )
    )
    if any(item is None for _, item in required):
        return LearningComparisonValidity.INVALID, ("arm validity evidence is missing",)
    invalid: list[str] = []
    descriptive: list[str] = []
    for arm_run_id, item in required:
        assert item is not None
        if not item.arm_isolated:
            invalid.append(f"arm isolation failed: {arm_run_id}")
        if not item.lineage_complete:
            invalid.append(f"learner-state lineage is incomplete: {arm_run_id}")
        if not item.probe_feedback_hidden:
            invalid.append(f"probe feedback was visible before scoring: {arm_run_id}")
        if not item.probe_state_discarded:
            invalid.append(f"probe-generated learner state was committed: {arm_run_id}")
        if item.hidden_evaluation_leaked:
            invalid.append(f"hidden evaluation data entered learner state: {arm_run_id}")
    if not relations_reviewed:
        descriptive.append("learning-family relations are not reviewed")
    if comparator_evidence is not None and focal_evidence is not None:
        if focal_evidence.adapter_id != comparator_evidence.adapter_id:
            descriptive.append("execution adapter differs between matched arms")
        if focal_evidence.initial_state_equivalence_id != comparator_evidence.initial_state_equivalence_id:
            descriptive.append("initial learner states are not independently equivalent")
    if comparator_plan is not None and (
        focal_plan.arm_role is not StudyArmRole.EXPOSURE or comparator_plan.arm_role is not StudyArmRole.CONTROL
    ):
        descriptive.append("between-arm comparison is not exposure versus matched cold control")
    records = (focal_record,) if comparator_record is None else (focal_record, comparator_record)
    for record in records:
        if record.agent.model != plan.spec.agent.model or record.agent.adapter != plan.spec.agent.adapter:
            descriptive.append(f"recorded agent differs from the compiled study: {record.trial_id}")
        if record.environment.compute_backend != plan.spec.compute.backend:
            descriptive.append(f"recorded compute backend differs from the compiled study: {record.trial_id}")
    if require_matching_task and comparator_record is not None and comparator_record.task_id != focal_record.task_id:
        invalid.append("matched probe records refer to different task identities")
    if invalid:
        return LearningComparisonValidity.INVALID, tuple(invalid + descriptive)
    if descriptive:
        return LearningComparisonValidity.DESCRIPTIVE_ONLY, tuple(descriptive)
    return LearningComparisonValidity.CONTROLLED, ()


def _normalised_effect(*, focal: float, comparator: float | None, direction: ImprovementDirection) -> float:
    if comparator is None:
        return focal
    return focal - comparator if direction is ImprovementDirection.HIGHER else comparator - focal


def _bound_diagnostics(
    focal: ProjectionResult,
    comparator: ProjectionResult | None,
) -> tuple[str, ...]:
    values = (focal,) if comparator is None else (focal, comparator)
    diagnostics: list[str] = []
    if all(
        item.upper_bound is not None and item.value is not None and item.value >= item.upper_bound for item in values
    ):
        diagnostics.append("all included values are at the declared projection ceiling")
    if all(
        item.lower_bound is not None and item.value is not None and item.value <= item.lower_bound for item in values
    ):
        diagnostics.append("all included values are at the declared projection floor")
    return tuple(diagnostics)


def _least_valid(
    left: LearningComparisonValidity,
    right: LearningComparisonValidity,
) -> LearningComparisonValidity:
    rank = {
        LearningComparisonValidity.CONTROLLED: 0,
        LearningComparisonValidity.DESCRIPTIVE_ONLY: 1,
        LearningComparisonValidity.INVALID: 2,
    }
    return left if rank[left] >= rank[right] else right


def _mean_or_none(values: list[float]) -> float | None:
    return None if not values else statistics.fmean(values)


def _empty_result(
    measurement: LearningMeasurementSpec,
    validity: LearningComparisonValidity,
    diagnostics: tuple[str, ...],
) -> LearningMeasurementResult:
    return LearningMeasurementResult(
        measurement_id=measurement.measurement_id,
        validity=validity,
        projection_id=measurement.projection_id,
        included_pairs=(),
        excluded_repetitions=(),
        focal_mean=None,
        comparator_mean=None,
        mean_effect=None,
        diagnostics=diagnostics,
    )


__all__ = (
    "AssessmentArmEvidence",
    "OutcomeProjection",
    "ProjectionResult",
    "assess_learning_study",
    "project_trial_reward",
)
