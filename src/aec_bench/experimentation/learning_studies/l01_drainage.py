# ABOUTME: Composes and assesses the first lifecycle-backed Learning Study vertical slice.
# ABOUTME: Keeps L01 treatment, projection, and evidence policy in explicit study-owned glue.

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import ExperienceRole, LearningStudySpec
from aec_bench.contracts.learning_study_assessment import LearningStudyAssessment
from aec_bench.contracts.learning_study_evidence import (
    FeedbackReleaseRecord,
    LearnerStateRef,
    LearnerTransitionReceipt,
    RecordedStudyExecution,
    StudyStepReceipt,
    StudyStepStatus,
)
from aec_bench.contracts.trial_record import EvaluationStatus, TrialRecord
from aec_bench.experimentation.learning_studies.assessment import (
    AssessmentArmEvidence,
    OutcomeProjection,
    ProjectionResult,
    assess_learning_study,
)
from aec_bench.experimentation.learning_studies.lifecycle_learning_state import (
    validate_lifecycle_learner_state,
)
from aec_bench.experimentation.learning_studies.lifecycles import (
    LifecycleConsolidationOperation,
    LifecycleExecutionCondition,
    LifecycleFeedback,
    LifecycleLearningBinding,
    LifecycleLearningTreatmentKind,
    build_lifecycle_learning_operations,
    resolve_lifecycle_learning_target,
)
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
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.lifecycles.stormwater_design.drainage_learning import (
    DRAINAGE_PROBE_TASK_ID,
    DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID,
    drainage_gate_score,
    drainage_staged_review_feedback,
    validate_drainage_staged_review_feedback,
)

L01_DRAINAGE_PROTOCOL_ID = "l01-drainage-staged-evidence-transfer"
L01_DRAINAGE_STUDY_ID = "l01-lifecycle-staged-evidence-transfer"
L01_CONSOLIDATION_OPERATION_ID = "update-lifecycle-review-memory"
L01_EXECUTION_CONDITION = LifecycleExecutionCondition(
    execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
    visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
)

_GATE_PROJECTIONS = {
    "drainage.staged-disclosure": "staged_disclosure",
    "drainage.finding-continuity": "finding_continuity",
    "drainage.closure-evidence": "closure_evidence",
    "drainage.claim-boundary": "claim_boundary",
}
_FORBIDDEN_LEARNER_MARKERS = (
    b"/hidden/",
    b"expected_answer",
    b"gold-submissions",
    b"private_path",
    b"semantic_no_op_release",
    b"verifier-config",
)
_FORBIDDEN_LEARNER_FILENAMES = {
    "experiment-manifest.json",
    "gold-submissions.json",
    "metrics.json",
    "verification.json",
}
ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True)
class L01DrainageRun:
    spec: LearningStudySpec
    plan: CompiledLearningStudy
    execution: LearningStudyExecution[LifecycleFeedback]
    arm_evidence: Mapping[str, AssessmentArmEvidence]
    unreviewed_assessment: LearningStudyAssessment
    reviewed_assessment: LearningStudyAssessment


def load_l01_drainage_protocol(
    *,
    agent: AgentConfig,
    compute: ComputeConfig,
    repetitions: int = 1,
) -> LearningStudySpec:
    """Load the maintained L01 protocol with one explicit run configuration."""

    return load_learning_study_protocol(
        BUILTIN_LEARNING_STUDY_PROTOCOLS / L01_DRAINAGE_PROTOCOL_ID,
        agent=agent,
        compute=compute,
        repetitions=repetitions,
    )


def compile_l01_drainage_study(
    *,
    study_run_id: str,
    agent: AgentConfig,
    compute: ComputeConfig,
    repetitions: int = 1,
) -> CompiledLearningStudy:
    """Compile L01 into ordinary planned lifecycle trials."""

    spec = load_l01_drainage_protocol(agent=agent, compute=compute, repetitions=repetitions)
    return compile_learning_study(
        study_run_id=study_run_id,
        spec=spec,
        resolve_task=resolve_lifecycle_learning_target,
    )


def build_l01_drainage_binding(
    *,
    run_root: Path,
    consolidation_operation: LifecycleConsolidationOperation,
    adapter_builder: Callable[..., Any] | None = None,
    resume_existing_run: bool = False,
) -> LifecycleLearningBinding:
    """Bind L01's two treatments, one feedback view, and one consolidation operation."""

    return build_lifecycle_learning_operations(
        run_root=run_root,
        execution_condition=L01_EXECUTION_CONDITION,
        treatment_kinds={
            "reset": LifecycleLearningTreatmentKind.RESET,
            "structured-memory": LifecycleLearningTreatmentKind.STRUCTURED_MEMORY,
        },
        feedback_projectors={DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID: drainage_staged_review_feedback},
        consolidation_operations={L01_CONSOLIDATION_OPERATION_ID: consolidation_operation},
        adapter_builder=adapter_builder,
        resume_existing_run=resume_existing_run,
    )


def l01_drainage_outcome_projections() -> dict[str, OutcomeProjection]:
    """Return the explicit L01 projection mapping without global registration."""

    projections: dict[str, OutcomeProjection] = {
        "lifecycle.canonical-reward": _project_probe_reward,
    }
    projections.update(
        {projection_id: _gate_projection(gate_id) for projection_id, gate_id in _GATE_PROJECTIONS.items()}
    )
    return projections


async def run_l01_drainage_study(
    *,
    run_root: Path,
    study_run_id: str,
    agent: AgentConfig,
    compute: ComputeConfig,
    consolidation_operation: LifecycleConsolidationOperation,
    adapter_builder: Callable[..., Any] | None = None,
    repetitions: int = 1,
) -> L01DrainageRun:
    """Run, record, and assess L01 under both relation-review states."""

    plan = compile_l01_drainage_study(
        study_run_id=study_run_id,
        agent=agent,
        compute=compute,
        repetitions=repetitions,
    )
    binding = build_l01_drainage_binding(
        run_root=run_root,
        consolidation_operation=consolidation_operation,
        adapter_builder=adapter_builder,
    )
    recorder = StudyRunRecorder(
        root=run_root,
        plan=plan,
        snapshot_state=binding.snapshot_state,
        feedback_artifacts=binding.feedback_artifacts,
    )
    execution = await run_learning_study(plan=plan, operations=binding.operations, observer=recorder)
    arm_evidence = build_l01_assessment_arm_evidence(
        run_root=run_root,
        plan=plan,
        execution=execution,
    )
    projections = l01_drainage_outcome_projections()
    assessment_execution = cast(LearningStudyExecution[object], execution)
    return L01DrainageRun(
        spec=plan.spec,
        plan=plan,
        execution=execution,
        arm_evidence=arm_evidence,
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


def run_l01_drainage_study_sync(**kwargs: Any) -> L01DrainageRun:
    """Run L01 from synchronous research and test entry points."""

    return asyncio.run(run_l01_drainage_study(**kwargs))


def build_l01_assessment_arm_evidence(
    *,
    run_root: Path,
    plan: CompiledLearningStudy,
    execution: LearningStudyExecution[LifecycleFeedback],
) -> dict[str, AssessmentArmEvidence]:
    """Derive every assessment fact from the completed plan and persisted evidence."""

    root = Path(run_root).resolve(strict=True)
    if plan.spec.study_id != L01_DRAINAGE_STUDY_ID or execution.study_run_id != plan.study_run_id:
        raise ValueError("assessment-evidence-incomplete: inputs do not identify L01")
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
            adapter_id=L01_EXECUTION_CONDITION.adapter_id,
            initial_state_equivalence_id=f"lifecycle-initial-state:{initial_ref.artifact.sha256}",
            arm_isolated=_arm_isolated(root, arm_run, arm_result),
            lineage_complete=_lineage_complete(root, plan, arm_run, arm_result),
            probe_feedback_hidden=_probe_feedback_hidden(root, plan.spec, arm_run, arm_result),
            probe_state_discarded=_probe_state_discarded(root, arm_run),
            hidden_evaluation_leaked=not _hidden_evaluation_absent(root, arm_run),
        )
    return evidence


def _project_probe_reward(record: TrialRecord) -> ProjectionResult:
    if record.task_id != DRAINAGE_PROBE_TASK_ID:
        return _ineligible(f"projection-task-mismatch: {record.task_id}")
    if record.evaluation_status is not EvaluationStatus.COMPLETED or record.evaluation is None:
        return _ineligible("projection-evaluation-missing: lifecycle evaluation is unavailable")
    if not record.evaluation.validity.verifier_completed:
        return _ineligible("projection-evaluation-missing: lifecycle verifier did not complete")
    reward = record.evaluation.reward
    if isinstance(reward, bool) or not isinstance(reward, int | float) or not math.isfinite(reward):
        return _ineligible("projection-value-invalid: canonical reward is not finite")
    value = float(reward)
    if not 0.0 <= value <= 1.0:
        return _ineligible("projection-value-out-of-bounds: canonical reward is outside [0, 1]")
    return ProjectionResult(eligible=True, value=value, lower_bound=0.0, upper_bound=1.0)


def _gate_projection(gate_id: str) -> OutcomeProjection:
    def project(record: TrialRecord) -> ProjectionResult:
        if record.task_id != DRAINAGE_PROBE_TASK_ID:
            return _ineligible(f"projection-task-mismatch: {record.task_id}")
        try:
            value = drainage_gate_score(record, gate_id)
        except ValueError as error:
            return _ineligible(str(error))
        return ProjectionResult(eligible=True, value=value, lower_bound=0.0, upper_bound=1.0)

    return project


def _ineligible(reason: str) -> ProjectionResult:
    return ProjectionResult(eligible=False, value=None, reason=reason)


def _arm_isolated(root: Path, arm_run: PlannedArmRun, result: ArmRunExecutionResult[LifecycleFeedback]) -> bool:
    try:
        arm_root = root / "learner-arms" / arm_run.arm_run_id
        if (
            not arm_root.is_dir()
            or arm_root.is_symlink()
            or arm_root.resolve(strict=True).parent != (root / "learner-arms")
        ):
            return False
        for step_result in result.completed_steps:
            if step_result.trial_record is None:
                continue
            expected = arm_root / "lifecycle-experiences" / step_result.step_id
            package = expected / "package"
            run = expected / "run"
            output = step_result.trial_record.output
            if (
                not package.is_dir()
                or package.is_symlink()
                or not run.is_dir()
                or run.is_symlink()
                or output is None
                or output.agent_output is None
                or Path(output.agent_output.output_path).resolve(strict=True) != run.resolve(strict=True)
            ):
                return False
        return True
    except (OSError, ValueError):
        return False


def _lineage_complete(
    root: Path,
    plan: CompiledLearningStudy,
    arm_run: PlannedArmRun,
    result: ArmRunExecutionResult[LifecycleFeedback],
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
    result: ArmRunExecutionResult[LifecycleFeedback],
) -> bool:
    probe_ids = {item.experience_id for item in spec.experiences if item.role is ExperienceRole.PROBE}
    if any(isinstance(step, CompiledFeedbackStep) and step.source_experience_id in probe_ids for step in arm_run.steps):
        return False
    probe_trial_ids = {
        step_result.trial_record.trial_id
        for step_result in result.completed_steps
        if step_result.trial_record is not None and step_result.trial_record.task_id == DRAINAGE_PROBE_TASK_ID
    }
    try:
        for feedback_path in (root / "feedback").glob("*.json"):
            feedback = _read_model(feedback_path, FeedbackReleaseRecord)
            if feedback.arm_run_id == arm_run.arm_run_id and (
                feedback.source_experience_id in probe_ids or feedback.source_trial_id in probe_trial_ids
            ):
                return False
        arm_root = root / "learner-arms" / arm_run.arm_run_id
        for step in arm_run.steps:
            if not isinstance(step, CompiledExperienceStep) or step.role is not ExperienceRole.PROBE:
                continue
            context = arm_root / "lifecycle-experiences" / step.step_id / "context"
            if context.exists() and any("feedback" in path.relative_to(context).parts for path in context.rglob("*")):
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
            validate_lifecycle_learner_state(state_root)
            for path in (item for item in state_root.rglob("*") if item.is_file()):
                if path.name in _FORBIDDEN_LEARNER_FILENAMES:
                    return False
                data = path.read_bytes()
                if any(marker in data.lower() for marker in _FORBIDDEN_LEARNER_MARKERS):
                    return False
                if path.parent.name == "feedback":
                    validate_drainage_staged_review_feedback(data)
        for context in (arm_root / "lifecycle-experiences").glob("*/context"):
            for path in (item for item in context.rglob("*") if item.is_file()):
                if path.name in _FORBIDDEN_LEARNER_FILENAMES:
                    return False
                data = path.read_bytes().lower()
                if any(marker in data for marker in _FORBIDDEN_LEARNER_MARKERS):
                    return False
        return True
    except (OSError, ValueError):
        return False


def _read_model(path: Path, model_type: type[ModelT]) -> ModelT:
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


__all__ = (
    "L01_CONSOLIDATION_OPERATION_ID",
    "L01_DRAINAGE_PROTOCOL_ID",
    "L01_DRAINAGE_STUDY_ID",
    "L01_EXECUTION_CONDITION",
    "L01DrainageRun",
    "build_l01_assessment_arm_evidence",
    "build_l01_drainage_binding",
    "compile_l01_drainage_study",
    "l01_drainage_outcome_projections",
    "load_l01_drainage_protocol",
    "run_l01_drainage_study",
    "run_l01_drainage_study_sync",
)
