# ABOUTME: Reconstructs Learning Study runtime state from authoritative receipts and exact artifacts.
# ABOUTME: Repairs interrupted commits without rerunning steps that have final step receipts.

from __future__ import annotations

import io
import json
import tarfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Generic, TypeVar

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.learning_study import LearningStudySpec
from aec_bench.contracts.learning_study_evidence import (
    FeedbackReleaseRecord,
    LearnerStateRef,
    LearnerTransitionReceipt,
    StudyStepReceipt,
    StudyStepStatus,
)
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.errors import LearningStudyPersistenceError
from aec_bench.experimentation.learning_studies.planning import (
    CompiledExperienceStep,
    CompiledFeedbackStep,
    CompiledLearningStudy,
    PlannedArmRun,
    compiled_learning_study_to_data,
)
from aec_bench.experimentation.learning_studies.recording import StudyRunRecorder
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunExecutionResult,
    ArmRunResumeState,
    ArmRunStatus,
    FeedbackHandle,
    LearnerStateHandle,
    LearningStudyResume,
    StepExecutionResult,
    StepExecutionStatus,
    StudyStepFailure,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.reader import read_trial_record

StateT = TypeVar("StateT")
FeedbackT = TypeVar("FeedbackT")


class ResumableStudy(Generic[StateT, FeedbackT]):
    def __init__(
        self,
        *,
        recorder: StudyRunRecorder[StateT, FeedbackT],
        resume: LearningStudyResume[StateT, FeedbackT],
    ) -> None:
        self.recorder = recorder
        self.resume = resume


def load_resumable_study(
    *,
    root: Path,
    plan: CompiledLearningStudy,
    restore_root: Path,
    snapshot_state: Callable[[LearnerStateHandle[StateT]], Path],
    restore_state: Callable[[LearnerStateRef, Path], LearnerStateHandle[StateT]],
    restore_feedback: Callable[
        [FeedbackReleaseRecord, LearnerStateHandle[StateT]],
        FeedbackHandle[FeedbackT],
    ],
    feedback_artifacts: Callable[[FeedbackHandle[FeedbackT]], tuple[ArtifactRef, ...]] | None = None,
) -> ResumableStudy[StateT, FeedbackT]:
    """Load exact plan evidence and return the observer plus runtime resume value."""

    selected_root = Path(root).absolute()
    _validate_persisted_plan(selected_root, plan)
    recorder = StudyRunRecorder(
        root=selected_root,
        plan=plan,
        snapshot_state=snapshot_state,
        feedback_artifacts=feedback_artifacts,
    )
    recorder.finish_pending_transactions()
    recorder.repair_missing_events()
    repository = ArtifactRepository(selected_root / "_artifacts")
    state_refs = _load_state_refs(selected_root, repository)
    transition_refs = _load_transitions(selected_root)
    feedback_refs = _load_feedback(selected_root, repository)
    completed_arm_runs: dict[str, ArmRunExecutionResult[FeedbackT]] = {}
    incomplete_arm_runs: dict[str, ArmRunResumeState[StateT, FeedbackT]] = {}
    known_state_ids = set(state_refs)
    known_state_ids.update(item.candidate_state_id for item in transition_refs.values())
    known_feedback_ids = set(feedback_refs)

    for arm_run in plan.arm_runs:
        arm_state_refs = {key: value for key, value in state_refs.items() if value.arm_run_id == arm_run.arm_run_id}
        initial_refs = [item for item in arm_state_refs.values() if item.parent_state_id is None]
        receipts = _load_receipt_prefix(selected_root, plan.study_run_id, arm_run)
        if not initial_refs:
            if receipts:
                raise LearningStudyPersistenceError("committed steps have no initial learner-state receipt")
            continue
        if len(initial_refs) != 1:
            raise LearningStudyPersistenceError("arm run must have exactly one initial learner state")
        initial_ref = initial_refs[0]
        current_state_id = initial_ref.state_id
        step_results: list[StepExecutionResult[FeedbackT]] = []
        trial_records: list[TrialRecord] = []
        feedback_records_by_step: list[tuple[str, FeedbackReleaseRecord]] = []
        terminal_failure: StudyStepFailure | None = None

        for receipt in receipts:
            planned_step = arm_run.steps[receipt.step_index]
            if receipt.status is StudyStepStatus.FAILED:
                assert receipt.failure is not None
                terminal_failure = StudyStepFailure(
                    category=receipt.failure.category,
                    message=receipt.failure.message,
                    arm_run_id=arm_run.arm_run_id,
                    step_id=receipt.step_id,
                )
                step_results.append(
                    StepExecutionResult(
                        step_id=receipt.step_id,
                        step_index=receipt.step_index,
                        kind=receipt.step_kind,
                        status=StepExecutionStatus.FAILED,
                        state_before_id=current_state_id,
                        candidate_state_id=None,
                        committed_state_id=current_state_id,
                        state_committed=False,
                        failure=terminal_failure,
                    )
                )
                break
            transition = _required_transition(receipt, transition_refs)
            if transition.state_before_id != current_state_id:
                raise LearningStudyPersistenceError("learner-state transition does not continue the committed lineage")
            if transition.committed:
                committed_id = transition.committed_state_id
                if committed_id is None or committed_id not in arm_state_refs:
                    raise LearningStudyPersistenceError("committed learner-state reference is missing")
                state_ref = arm_state_refs[committed_id]
                if state_ref.parent_state_id != current_state_id or state_ref.created_after_step_id != receipt.step_id:
                    raise LearningStudyPersistenceError("learner-state reference does not match its transition")
                current_state_id = committed_id
            trial = _load_trial(selected_root, planned_step, receipt)
            if trial is not None:
                trial_records.append(trial)
            feedback_record = None if receipt.feedback_id is None else feedback_refs.get(receipt.feedback_id)
            if receipt.feedback_id is not None and feedback_record is None:
                raise LearningStudyPersistenceError("feedback release receipt is missing")
            step_results.append(
                StepExecutionResult(
                    step_id=receipt.step_id,
                    step_index=receipt.step_index,
                    kind=receipt.step_kind,
                    status=StepExecutionStatus.COMPLETED,
                    state_before_id=transition.state_before_id,
                    candidate_state_id=transition.candidate_state_id,
                    committed_state_id=transition.committed_state_id,
                    state_committed=transition.committed,
                    changed_channels=transition.changed_channels,
                    trial_record=trial,
                    diagnostics=transition.diagnostics,
                )
            )
            if feedback_record is not None:
                # Feedback values are restored after the current committed snapshot is materialised.
                feedback_records_by_step.append((planned_step.step_id, feedback_record))

        current_ref = arm_state_refs[current_state_id]
        state_directory = _restore_archive(
            repository=repository,
            state_ref=current_ref,
            destination=Path(restore_root).absolute() / arm_run.arm_run_id / current_state_id,
        )
        restored_handle = restore_state(current_ref, state_directory)
        if restored_handle.state_id != current_state_id:
            raise LearningStudyPersistenceError("adapter restored a different learner-state identity")
        restored_feedback: list[tuple[str, FeedbackHandle[FeedbackT]]] = []
        for step_id, feedback_record in feedback_records_by_step:
            handle = restore_feedback(feedback_record, restored_handle)
            if handle.feedback_id != feedback_record.feedback_id:
                raise LearningStudyPersistenceError("adapter restored a different feedback identity")
            restored_feedback.append((step_id, handle))
            for index, step_result in enumerate(step_results):
                if step_result.step_id == step_id:
                    step_results[index] = replace(step_result, feedback=handle)

        terminal = terminal_failure is not None or len(receipts) == len(arm_run.steps)
        if terminal:
            if terminal_failure is not None:
                for skipped_index, skipped in enumerate(
                    arm_run.steps[len(receipts) :],
                    start=len(receipts),
                ):
                    step_results.append(
                        StepExecutionResult(
                            step_id=skipped.step_id,
                            step_index=skipped_index,
                            kind=_step_kind(skipped),
                            status=StepExecutionStatus.SKIPPED,
                            state_before_id=current_state_id,
                            candidate_state_id=None,
                            committed_state_id=current_state_id,
                            state_committed=None,
                        )
                    )
            completed_arm_runs[arm_run.arm_run_id] = ArmRunExecutionResult(
                arm_run_id=arm_run.arm_run_id,
                status=ArmRunStatus.FAILED if terminal_failure is not None else ArmRunStatus.COMPLETED,
                initial_state_id=initial_ref.state_id,
                completed_steps=tuple(step_results),
                trial_records=tuple(trial_records),
                final_state_id=current_state_id,
                failure=terminal_failure,
            )
        else:
            incomplete_arm_runs[arm_run.arm_run_id] = ArmRunResumeState(
                initial_state_id=initial_ref.state_id,
                current_state=restored_handle,
                completed_steps=tuple(step_results),
                trial_records=tuple(trial_records),
                feedback_by_step=tuple(restored_feedback),
            )

    return ResumableStudy(
        recorder=recorder,
        resume=LearningStudyResume(
            completed_arm_runs=completed_arm_runs,
            incomplete_arm_runs=incomplete_arm_runs,
            known_state_ids=frozenset(known_state_ids),
            known_feedback_ids=frozenset(known_feedback_ids),
        ),
    )


def _validate_persisted_plan(root: Path, plan: CompiledLearningStudy) -> None:
    spec_path = root / "study-spec.json"
    plan_path = root / "study-plan.json"
    if not spec_path.is_file() or not plan_path.is_file():
        raise LearningStudyPersistenceError("study spec or compiled plan is missing")
    persisted_spec = LearningStudySpec.model_validate(_read_json(spec_path))
    if persisted_spec != plan.spec:
        raise LearningStudyPersistenceError("persisted study spec differs from the requested plan")
    if _read_json(plan_path) != compiled_learning_study_to_data(plan):
        raise LearningStudyPersistenceError("persisted compiled plan differs from the requested plan")


def _load_state_refs(root: Path, repository: ArtifactRepository) -> dict[str, LearnerStateRef]:
    result: dict[str, LearnerStateRef] = {}
    for path in sorted((root / "states").glob("*.json")):
        reference = LearnerStateRef.model_validate_json(path.read_text(encoding="utf-8"))
        if reference.state_id in result:
            raise LearningStudyPersistenceError("duplicate learner-state identity")
        repository.read_bytes(reference.artifact)
        result[reference.state_id] = reference
    return result


def _load_transitions(root: Path) -> dict[str, LearnerTransitionReceipt]:
    result: dict[str, LearnerTransitionReceipt] = {}
    for path in sorted((root / "transitions").glob("*.json")):
        receipt = LearnerTransitionReceipt.model_validate_json(path.read_text(encoding="utf-8"))
        if receipt.transition_id in result:
            raise LearningStudyPersistenceError("duplicate learner transition identity")
        result[receipt.transition_id] = receipt
    return result


def _load_feedback(root: Path, repository: ArtifactRepository) -> dict[str, FeedbackReleaseRecord]:
    result: dict[str, FeedbackReleaseRecord] = {}
    for path in sorted((root / "feedback").glob("*.json")):
        record = FeedbackReleaseRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if record.feedback_id in result:
            raise LearningStudyPersistenceError("duplicate feedback identity")
        for reference in record.public_artifact_refs:
            repository.read_bytes(reference)
        result[record.feedback_id] = record
    return result


def _load_receipt_prefix(root: Path, study_run_id: str, arm_run: PlannedArmRun) -> list[StudyStepReceipt]:
    receipts: list[StudyStepReceipt] = []
    arm_root = root / "steps" / arm_run.arm_run_id
    for index, step in enumerate(arm_run.steps):
        path = arm_root / f"{index:03d}-{step.step_id}.json"
        if not path.is_file():
            if any(arm_root.glob(f"{index:03d}-*.json")):
                raise LearningStudyPersistenceError("step receipt identity differs from the compiled plan")
            break
        receipt = StudyStepReceipt.model_validate_json(path.read_text(encoding="utf-8"))
        if (
            receipt.study_run_id != study_run_id
            or receipt.arm_run_id != arm_run.arm_run_id
            or receipt.step_id != step.step_id
            or receipt.step_index != index
        ):
            raise LearningStudyPersistenceError("step receipt differs from the compiled plan")
        receipts.append(receipt)
        if receipt.status is StudyStepStatus.FAILED:
            break
    if len(list(arm_root.glob("*.json"))) != len(receipts):
        raise LearningStudyPersistenceError("step receipts are not a contiguous plan prefix")
    return receipts


def _required_transition(
    receipt: StudyStepReceipt,
    transitions: dict[str, LearnerTransitionReceipt],
) -> LearnerTransitionReceipt:
    if receipt.transition_id is None or receipt.transition_id not in transitions:
        raise LearningStudyPersistenceError("completed step has no learner-transition receipt")
    transition = transitions[receipt.transition_id]
    if transition.arm_run_id != receipt.arm_run_id or transition.step_id != receipt.step_id:
        raise LearningStudyPersistenceError("learner transition differs from its step receipt")
    return transition


def _load_trial(root: Path, planned_step: object, receipt: StudyStepReceipt) -> TrialRecord | None:
    if receipt.trial_id is None:
        return None
    if not isinstance(planned_step, CompiledExperienceStep) or receipt.trial_id != planned_step.trial.trial_id:
        raise LearningStudyPersistenceError("trial receipt differs from the compiled experience")
    path = root / "ledger" / planned_step.trial.experiment_id / f"{receipt.trial_id}.json"
    record = read_trial_record(path, ledger_root=root / "ledger")
    if record.task_id != planned_step.trial.task_id:
        raise LearningStudyPersistenceError("trial task differs from the compiled experience")
    return record


def _restore_archive(*, repository: ArtifactRepository, state_ref: LearnerStateRef, destination: Path) -> Path:
    payload = repository.read_bytes(state_ref.artifact)
    if destination.exists() and any(destination.iterdir()):
        raise LearningStudyPersistenceError(f"learner restore destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    seen: set[PurePosixPath] = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
            for member in archive.getmembers():
                relative = PurePosixPath(member.name)
                if relative.is_absolute() or ".." in relative.parts or relative in seen:
                    raise LearningStudyPersistenceError("learner snapshot archive contains an unsafe path")
                seen.add(relative)
                if not member.isdir() and not member.isfile():
                    raise LearningStudyPersistenceError("learner snapshot archive contains a non-file entry")
                target = destination.joinpath(*relative.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise LearningStudyPersistenceError("learner snapshot archive file is unavailable")
                target.write_bytes(source.read())
    except (tarfile.TarError, OSError) as error:
        raise LearningStudyPersistenceError("learner snapshot archive is invalid") from error
    return destination


def _step_kind(step: object) -> str:
    if isinstance(step, CompiledExperienceStep):
        return "run_experience"
    if isinstance(step, CompiledFeedbackStep):
        return "release_feedback"
    return "consolidate"


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LearningStudyPersistenceError(f"study evidence is invalid: {path}") from error


__all__ = ("ResumableStudy", "load_resumable_study")
