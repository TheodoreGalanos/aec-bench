# ABOUTME: Composes and assesses the W02 dam-seepage structural-transfer Learning Study.
# ABOUTME: Keeps W02 treatment, projection, and evidence policy in explicit study-owned glue.

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import ExperienceRole, LearningStudySpec
from aec_bench.contracts.learning_study_assessment import LearningStudyAssessment, ProjectionResult
from aec_bench.contracts.learning_study_evidence import (
    FeedbackReleaseRecord,
    LearnerStateRef,
    LearnerTransitionReceipt,
    RecordedStudyExecution,
    StudyStepReceipt,
    StudyStepStatus,
)
from aec_bench.contracts.trial_record import EvaluationStatus, ExecutionStatus, TrialRecord
from aec_bench.experimentation.learning_studies.assessment import (
    AssessmentArmEvidence,
    OutcomeProjection,
    assess_learning_study,
)
from aec_bench.experimentation.learning_studies.learner_state import validate_learner_state
from aec_bench.experimentation.learning_studies.planning import (
    CompiledConsolidationStep,
    CompiledExperienceStep,
    CompiledFeedbackStep,
    CompiledLearningStudy,
    PlannedArmRun,
    compile_learning_study,
)
from aec_bench.experimentation.learning_studies.protocol_collection import (
    BUILTIN_LEARNING_STUDY_PROTOCOLS,
    load_learning_study_protocol,
)
from aec_bench.experimentation.learning_studies.recording import StudyRunRecorder
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunExecutionResult,
    ArmRunStatus,
    LearningStudyExecution,
    run_learning_study,
)
from aec_bench.experimentation.learning_studies.worlds import (
    WorldConsolidationOperation,
    WorldFeedback,
    WorldLearningBinding,
    WorldLearningExecutionCondition,
    WorldLearningTreatmentKind,
    build_world_learning_operations,
    resolve_world_learning_target,
    world_canonical_reward,
)
from aec_bench.harness.dam_seepage_trial import run_dam_seepage_trial
from aec_bench.worlds.monitoring.dam_seepage.dam_learning import (
    DAM_ESCALATION_BOUNDARY_FEEDBACK_VIEW_ID,
    dam_escalation_boundary_feedback,
    dam_evidence_complete,
    dam_response_correct,
    validate_dam_escalation_boundary_feedback,
)
from aec_bench.worlds.monitoring.dam_seepage.world import DAM_SEEPAGE_TASK_WORLD_ID, SeepageResponse

DAM_W02_PROTOCOL_ID = "w02-dam-structural-transfer"
DAM_W02_STUDY_ID = "w02-dam-structural-transfer"
DAM_W02_CONSOLIDATION_OPERATION_ID = "update-dam-monitoring-memory"
DAM_W02_ACQUISITION_TASK_ID = f"world/{DAM_SEEPAGE_TASK_WORLD_ID}/unreliable-instrument-escalation"
DAM_W02_PROBE_TASK_ID = f"world/{DAM_SEEPAGE_TASK_WORLD_ID}/unreliable-instrument-surface-transfer"

_DAM_PROJECTORS: dict[str, Callable[[TrialRecord], float]] = {
    "dam.response-correct": dam_response_correct,
    "dam.evidence-complete": dam_evidence_complete,
}
_FORBIDDEN_LEARNER_MARKERS = (
    b"/hidden/",
    b"expected_answer",
    b"expected_response",
    b"gold-submissions",
    b"private_path",
    b"verifier-config",
    b"required_response",
    b"instrument_condition",
    b"visual_alert_conditions",
    b"required_consecutive_alert_readings",
    b"reliable-routine-surveillance",
    b"unreliable-instrument-surface-transfer",
)
_FORBIDDEN_LEARNER_FILENAMES: frozenset[str] = frozenset({"dam-world-evidence.json"})
ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True)
class W02DamRun:
    spec: LearningStudySpec
    plan: CompiledLearningStudy
    execution: LearningStudyExecution[WorldFeedback]
    arm_evidence: Mapping[str, AssessmentArmEvidence]
    acquisition_fidelity: Mapping[str, W02AcquisitionFidelity]
    unreviewed_assessment: LearningStudyAssessment
    reviewed_assessment: LearningStudyAssessment


@dataclass(frozen=True, slots=True)
class W02AcquisitionFidelity:
    """Truthful acquisition facts derived from the arm's persisted TrialRecord."""

    arm_run_id: str
    trial_id: str | None
    trial_record_present: bool
    replay_valid: bool | None
    response_correct: bool | None
    evidence_complete: bool | None
    escalation_selected: bool | None
    acquisition_successful: bool

    @property
    def fidelity_satisfied(self) -> bool:
        """Return whether the acquisition supports a transfer claim."""

        return self.acquisition_successful


def load_w02_dam_protocol(
    *,
    agent: AgentConfig,
    compute: ComputeConfig,
    repetitions: int = 1,
) -> LearningStudySpec:
    """Load the maintained W02 protocol with one explicit run configuration."""

    return load_learning_study_protocol(
        BUILTIN_LEARNING_STUDY_PROTOCOLS / DAM_W02_PROTOCOL_ID,
        agent=agent,
        compute=compute,
        repetitions=repetitions,
    )


def compile_w02_dam_study(
    *,
    study_run_id: str,
    agent: AgentConfig,
    compute: ComputeConfig,
    repetitions: int = 1,
) -> CompiledLearningStudy:
    """Compile W02 into ordinary planned world trials."""

    spec = load_w02_dam_protocol(agent=agent, compute=compute, repetitions=repetitions)
    return compile_learning_study(
        study_run_id=study_run_id,
        spec=spec,
        resolve_task=resolve_world_learning_target,
    )


def build_w02_dam_binding(
    *,
    run_root: Path,
    execution_condition: WorldLearningExecutionCondition,
    consolidation_operation: WorldConsolidationOperation,
    resume_existing_run: bool = False,
) -> WorldLearningBinding:
    """Bind W02's two treatments, one feedback view, and one consolidation operation."""

    instruction = (
        "Review the dam-seepage monitoring point, gather enough measurement and visual evidence "
        "for the current response, and submit either engineering-review escalation or continued "
        "routine surveillance."
    )
    return build_world_learning_operations(
        run_root=run_root,
        world_id=DAM_SEEPAGE_TASK_WORLD_ID,
        execution_condition=execution_condition,
        run_trial=run_dam_seepage_trial,
        instructions={
            DAM_W02_ACQUISITION_TASK_ID: instruction,
            DAM_W02_PROBE_TASK_ID: instruction,
        },
        treatment_kinds={
            "reset": WorldLearningTreatmentKind.RESET,
            "structured-memory": WorldLearningTreatmentKind.STRUCTURED_MEMORY,
        },
        feedback_projectors={DAM_ESCALATION_BOUNDARY_FEEDBACK_VIEW_ID: dam_escalation_boundary_feedback},
        consolidation_operations={DAM_W02_CONSOLIDATION_OPERATION_ID: consolidation_operation},
        resume_existing_run=resume_existing_run,
    )


def w02_dam_outcome_projections() -> dict[str, OutcomeProjection]:
    """Return the explicit W02 projection mapping without global registration."""

    projections: dict[str, OutcomeProjection] = {"world.canonical-reward": _project_probe_reward}
    projections.update({projection_id: _dam_projection(reader) for projection_id, reader in _DAM_PROJECTORS.items()})
    return projections


async def run_w02_dam_study(
    *,
    run_root: Path,
    study_run_id: str,
    agent: AgentConfig,
    compute: ComputeConfig,
    execution_condition: WorldLearningExecutionCondition,
    consolidation_operation: WorldConsolidationOperation,
    repetitions: int = 1,
) -> W02DamRun:
    """Run, record, and assess W02 under both relation-review states."""

    plan = compile_w02_dam_study(
        study_run_id=study_run_id,
        agent=agent,
        compute=compute,
        repetitions=repetitions,
    )
    binding = build_w02_dam_binding(
        run_root=run_root,
        execution_condition=execution_condition,
        consolidation_operation=consolidation_operation,
    )
    recorder = StudyRunRecorder(
        root=run_root,
        plan=plan,
        snapshot_state=binding.snapshot_state,
        feedback_artifacts=binding.feedback_artifacts,
    )
    execution = await run_learning_study(plan=plan, operations=binding.operations, observer=recorder)
    arm_evidence = build_w02_assessment_arm_evidence(
        run_root=run_root,
        plan=plan,
        execution=execution,
        adapter_id=execution_condition.adapter_id,
    )
    acquisition_fidelity = build_w02_acquisition_fidelity(plan=plan, execution=execution)
    projections = w02_dam_outcome_projections()
    assessment_execution = cast(LearningStudyExecution[object], execution)
    return W02DamRun(
        spec=plan.spec,
        plan=plan,
        execution=execution,
        arm_evidence=arm_evidence,
        acquisition_fidelity=acquisition_fidelity,
        unreviewed_assessment=assess_learning_study(
            spec=plan.spec,
            plan=plan,
            execution=assessment_execution,
            projections=projections,
            arm_evidence=arm_evidence,
            relations_reviewed=False,
        ),
        reviewed_assessment=assess_learning_study(
            spec=plan.spec,
            plan=plan,
            execution=assessment_execution,
            projections=projections,
            arm_evidence=arm_evidence,
            relations_reviewed=True,
        ),
    )


def run_w02_dam_study_sync(**kwargs: Any) -> W02DamRun:
    """Run W02 from synchronous research and test entry points."""

    return asyncio.run(run_w02_dam_study(**kwargs))


def build_w02_acquisition_fidelity(
    *,
    plan: CompiledLearningStudy,
    execution: LearningStudyExecution[WorldFeedback],
) -> dict[str, W02AcquisitionFidelity]:
    """Derive acquisition fidelity from the real TrialRecords in each acquisition arm."""

    if plan.spec.study_id != DAM_W02_STUDY_ID or execution.study_run_id != plan.study_run_id:
        raise ValueError("acquisition-fidelity-incomplete: inputs do not identify W02")

    execution_by_arm: dict[str, ArmRunExecutionResult[WorldFeedback]] = {}
    for item in execution.arm_runs:
        if item.arm_run_id in execution_by_arm:
            raise ValueError(f"acquisition-fidelity-ambiguous: duplicate arm result: {item.arm_run_id}")
        execution_by_arm[item.arm_run_id] = item
    fidelity: dict[str, W02AcquisitionFidelity] = {}
    for arm_run in plan.arm_runs:
        acquisition_steps = tuple(
            step
            for step in arm_run.steps
            if isinstance(step, CompiledExperienceStep) and step.role is ExperienceRole.ACQUISITION
        )
        if not acquisition_steps:
            continue
        if len(acquisition_steps) != 1:
            raise ValueError(f"acquisition-fidelity-incomplete: expected one acquisition: {arm_run.arm_run_id}")

        step = acquisition_steps[0]
        arm_result = execution_by_arm.get(arm_run.arm_run_id)
        matching_records = (
            ()
            if arm_result is None
            else tuple(
                item
                for item in arm_result.trial_records
                if item.trial_id == step.trial.trial_id and item.task_id == DAM_W02_ACQUISITION_TASK_ID
            )
        )
        if len(matching_records) > 1:
            raise ValueError(f"acquisition-fidelity-ambiguous: expected one acquisition: {arm_run.arm_run_id}")
        record = matching_records[0] if matching_records else None
        if record is None:
            fidelity[arm_run.arm_run_id] = W02AcquisitionFidelity(
                arm_run_id=arm_run.arm_run_id,
                trial_id=None,
                trial_record_present=False,
                replay_valid=None,
                response_correct=None,
                evidence_complete=None,
                escalation_selected=None,
                acquisition_successful=False,
            )
            continue

        evaluation = record.evaluation if record.evaluation_status is EvaluationStatus.COMPLETED else None
        breakdown = None if evaluation is None else evaluation.breakdown
        breakdown = breakdown if isinstance(breakdown, dict) else None
        response_correct = _optional_bool(breakdown, "response_correct")
        evidence_complete = _optional_bool(breakdown, "evidence_complete")
        selected_response = None if breakdown is None else breakdown.get("selected_response")
        escalation_selected = (
            selected_response == SeepageResponse.ENGINEERING_REVIEW.value
            if isinstance(selected_response, str)
            else None
        )
        replay_valid = None if evaluation is None else evaluation.validity.verifier_completed
        execution_completed = record.execution_status is ExecutionStatus.COMPLETED
        evaluation_completed = record.evaluation_status is EvaluationStatus.COMPLETED
        acquisition_successful = (
            execution_completed
            and evaluation_completed
            and replay_valid is True
            and response_correct is True
            and evidence_complete is True
            and escalation_selected is True
        )
        fidelity[arm_run.arm_run_id] = W02AcquisitionFidelity(
            arm_run_id=arm_run.arm_run_id,
            trial_id=record.trial_id,
            trial_record_present=True,
            replay_valid=replay_valid,
            response_correct=response_correct,
            evidence_complete=evidence_complete,
            escalation_selected=escalation_selected,
            acquisition_successful=acquisition_successful,
        )
    return fidelity


def build_w02_assessment_arm_evidence(
    *,
    run_root: Path,
    plan: CompiledLearningStudy,
    execution: LearningStudyExecution[WorldFeedback],
    adapter_id: str,
) -> dict[str, AssessmentArmEvidence]:
    """Derive every assessment fact from the completed plan and persisted evidence."""

    root = Path(run_root).resolve(strict=True)
    if plan.spec.study_id != DAM_W02_STUDY_ID or execution.study_run_id != plan.study_run_id:
        raise ValueError("assessment-evidence-incomplete: inputs do not identify W02")
    execution_by_arm = {item.arm_run_id: item for item in execution.arm_runs}
    evidence: dict[str, AssessmentArmEvidence] = {}
    for arm_run in plan.arm_runs:
        arm_result = execution_by_arm.get(arm_run.arm_run_id)
        if arm_result is None or arm_result.initial_state_id is None:
            raise ValueError(f"assessment-evidence-incomplete: arm result is missing: {arm_run.arm_run_id}")
        initial_ref = _read_model(
            root / "states" / f"{arm_result.initial_state_id}.json",
            LearnerStateRef,
        )
        if initial_ref.arm_run_id != arm_run.arm_run_id or initial_ref.parent_state_id is not None:
            raise ValueError(f"assessment-evidence-incomplete: initial state is invalid: {arm_run.arm_run_id}")
        evidence[arm_run.arm_run_id] = AssessmentArmEvidence(
            adapter_id=adapter_id,
            initial_state_equivalence_id=f"world-initial-state:{initial_ref.artifact.sha256}",
            arm_isolated=_arm_isolated(root, arm_run, arm_result),
            lineage_complete=_lineage_complete(root, plan, arm_run, arm_result),
            probe_feedback_hidden=_probe_feedback_hidden(root, plan.spec, arm_run, arm_result),
            probe_state_discarded=_probe_state_discarded(root, arm_run),
            hidden_evaluation_leaked=not _hidden_evaluation_absent(root, arm_run),
        )
    return evidence


def _project_probe_reward(record: TrialRecord) -> ProjectionResult:
    if record.task_id != DAM_W02_PROBE_TASK_ID:
        return _ineligible(f"projection-task-mismatch: {record.task_id}")
    try:
        value = world_canonical_reward(record)
    except ValueError as error:
        return _ineligible(str(error))
    return ProjectionResult(eligible=True, value=value, lower_bound=0.0, upper_bound=1.0)


def _dam_projection(reader: Callable[[TrialRecord], float]) -> OutcomeProjection:
    def project(record: TrialRecord) -> ProjectionResult:
        if record.task_id != DAM_W02_PROBE_TASK_ID:
            return _ineligible(f"projection-task-mismatch: {record.task_id}")
        try:
            value = reader(record)
        except ValueError as error:
            return _ineligible(str(error))
        return ProjectionResult(eligible=True, value=value, lower_bound=0.0, upper_bound=1.0)

    return project


def _ineligible(reason: str) -> ProjectionResult:
    return ProjectionResult(eligible=False, value=None, reason=reason)


def _arm_isolated(root: Path, arm_run: PlannedArmRun, result: ArmRunExecutionResult[WorldFeedback]) -> bool:
    try:
        arm_root = root / "learner-arms" / arm_run.arm_run_id
        learner_arms_root = (root / "learner-arms").resolve(strict=True)
        if not arm_root.is_dir() or arm_root.is_symlink() or arm_root.resolve(strict=True).parent != learner_arms_root:
            return False
        arm_root_resolved = arm_root.resolve(strict=True)
        for step_result in result.completed_steps:
            if step_result.trial_record is None:
                continue
            output = step_result.trial_record.output
            if output is None or output.agent_output is None:
                return False
            evidence_path = Path(output.agent_output.output_path).resolve(strict=True)
            if evidence_path == arm_root_resolved or arm_root_resolved in evidence_path.parents:
                return False
        return True
    except (OSError, ValueError):
        return False


def _lineage_complete(
    root: Path,
    plan: CompiledLearningStudy,
    arm_run: PlannedArmRun,
    result: ArmRunExecutionResult[WorldFeedback],
) -> bool:
    try:
        if result.status is not ArmRunStatus.COMPLETED or result.initial_state_id is None:
            return False
        if len(result.completed_steps) != len(arm_run.steps):
            return False
        current_state_id = result.initial_state_id
        for index, step in enumerate(arm_run.steps):
            receipt = _read_model(
                root / "steps" / arm_run.arm_run_id / f"{index:03d}-{step.step_id}.json",
                StudyStepReceipt,
            )
            if receipt.status is not StudyStepStatus.COMPLETED or receipt.transition_id is None:
                return False
            transition = _read_model(root / "transitions" / f"{receipt.transition_id}.json", LearnerTransitionReceipt)
            if transition.arm_run_id != arm_run.arm_run_id or transition.step_id != step.step_id:
                return False
            if transition.state_before_id != current_state_id:
                return False
            expected_kind = "consolidation"
            expected_committed = True
            if isinstance(step, CompiledExperienceStep):
                expected_kind = "experience" if step.commit_post_state else "probe_discard"
                expected_committed = step.commit_post_state
            elif isinstance(step, CompiledFeedbackStep):
                expected_kind = "feedback_release"
                if receipt.feedback_id is None:
                    return False
                feedback = _read_model(root / "feedback" / f"{receipt.feedback_id}.json", FeedbackReleaseRecord)
                if (
                    feedback.arm_run_id != arm_run.arm_run_id
                    or feedback.release_step_id != step.step_id
                    or feedback.source_experience_id != step.source_experience_id
                    or feedback.view_id != step.feedback_view_id
                    or feedback.state_before_id != current_state_id
                    or feedback.state_after_id != transition.committed_state_id
                ):
                    return False
            elif isinstance(step, CompiledConsolidationStep):
                expected_kind = "consolidation"
            if transition.operation_kind != expected_kind or transition.committed is not expected_committed:
                return False
            if expected_committed:
                state_ref = _read_model(
                    root / "states" / f"{transition.candidate_state_id}.json",
                    LearnerStateRef,
                )
                if state_ref.parent_state_id != current_state_id or state_ref.created_after_step_id != step.step_id:
                    return False
            if transition.committed_state_id is None:
                return False
            current_state_id = transition.committed_state_id
        recorded = _read_model(root / "result.json", RecordedStudyExecution)
        recorded_arm = next(item for item in recorded.arm_runs if item.arm_run_id == arm_run.arm_run_id)
        return result.final_state_id == current_state_id == recorded_arm.final_state_id
    except (OSError, StopIteration, ValueError):
        return False


def _probe_feedback_hidden(
    root: Path,
    spec: LearningStudySpec,
    arm_run: PlannedArmRun,
    result: ArmRunExecutionResult[WorldFeedback],
) -> bool:
    probe_ids = {item.experience_id for item in spec.experiences if item.role is ExperienceRole.PROBE}
    if any(isinstance(step, CompiledFeedbackStep) and step.source_experience_id in probe_ids for step in arm_run.steps):
        return False
    probe_trial_ids = {
        step_result.trial_record.trial_id
        for step_result in result.completed_steps
        if step_result.trial_record is not None and step_result.trial_record.task_id == DAM_W02_PROBE_TASK_ID
    }
    try:
        for feedback_path in (root / "feedback").glob("*.json"):
            feedback = _read_model(feedback_path, FeedbackReleaseRecord)
            if feedback.arm_run_id == arm_run.arm_run_id and (
                feedback.source_experience_id in probe_ids or feedback.source_trial_id in probe_trial_ids
            ):
                return False
        return True
    except (OSError, ValueError):
        return False


def _probe_state_discarded(root: Path, arm_run: PlannedArmRun) -> bool:
    try:
        arm_root = root / "learner-arms" / arm_run.arm_run_id
        for index, step in enumerate(arm_run.steps):
            if not isinstance(step, CompiledExperienceStep) or step.role is not ExperienceRole.PROBE:
                continue
            if step.commit_post_state:
                return False
            receipt = _read_model(
                root / "steps" / arm_run.arm_run_id / f"{index:03d}-{step.step_id}.json",
                StudyStepReceipt,
            )
            if receipt.transition_id is None:
                return False
            transition = _read_model(root / "transitions" / f"{receipt.transition_id}.json", LearnerTransitionReceipt)
            if transition.operation_kind != "probe_discard" or transition.committed:
                return False
            if (arm_root / "states" / step.step_id).exists():
                return False
        return True
    except (OSError, ValueError):
        return False


def _hidden_evaluation_absent(root: Path, arm_run: PlannedArmRun) -> bool:
    try:
        arm_root = root / "learner-arms" / arm_run.arm_run_id
        states_root = arm_root / "states"
        for state_root in (path for path in states_root.iterdir() if path.is_dir()):
            validate_learner_state(state_root)
            for path in (item for item in state_root.rglob("*") if item.is_file()):
                if path.name in _FORBIDDEN_LEARNER_FILENAMES:
                    return False
                data = path.read_bytes()
                if any(marker in data.lower() for marker in _FORBIDDEN_LEARNER_MARKERS):
                    return False
                if path.parent.name == "feedback":
                    validate_dam_escalation_boundary_feedback(data)
        return True
    except (OSError, ValueError):
        return False


def _optional_bool(breakdown: dict[str, Any] | None, field: str) -> bool | None:
    if breakdown is None:
        return None
    value = breakdown.get(field)
    return value if isinstance(value, bool) else None


def _read_model(path: Path, model_type: type[ModelT]) -> ModelT:
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


__all__ = (
    "DAM_W02_ACQUISITION_TASK_ID",
    "DAM_W02_CONSOLIDATION_OPERATION_ID",
    "DAM_W02_PROBE_TASK_ID",
    "DAM_W02_PROTOCOL_ID",
    "DAM_W02_STUDY_ID",
    "W02AcquisitionFidelity",
    "W02DamRun",
    "build_w02_acquisition_fidelity",
    "build_w02_assessment_arm_evidence",
    "build_w02_dam_binding",
    "compile_w02_dam_study",
    "load_w02_dam_protocol",
    "run_w02_dam_study",
    "run_w02_dam_study_sync",
    "w02_dam_outcome_projections",
)
