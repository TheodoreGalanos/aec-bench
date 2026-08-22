# ABOUTME: Persists append-only Learning Study evidence through existing artifact and trial ledgers.
# ABOUTME: Uses a final step receipt as the atomic resume authority for each callback result.

from __future__ import annotations

import io
import json
import os
import re
import tarfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.learning_study_evidence import (
    FeedbackReleaseRecord,
    LearnerStateRef,
    LearnerTransitionReceipt,
    RecordedArmRunResult,
    RecordedStudyExecution,
    StudyEvent,
    StudyEventKind,
    StudyRunStatus,
    StudyStepFailureRecord,
    StudyStepReceipt,
    StudyStepStatus,
)
from aec_bench.contracts.trial_record import RunManifest, TrialRecord
from aec_bench.experimentation.learning_studies.errors import LearningStudyPersistenceError
from aec_bench.experimentation.learning_studies.planning import (
    CompiledConsolidationStep,
    CompiledExperienceStep,
    CompiledFeedbackStep,
    CompiledLearningStudy,
    CompiledStudyStep,
    PlannedArmRun,
    compiled_learning_study_to_data,
)
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunExecutionResult,
    ArmRunStatus,
    FeedbackHandle,
    LearnerStateHandle,
    LearningStudyExecution,
    LearningStudyObserver,
    StepExecutionResult,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.durability import fsync_directory, mkdir_durable
from aec_bench.ledger.reader import read_trial_record
from aec_bench.ledger.writer import DuplicateTrialRecordError, materialize_trial_record, write_trial_record

StateT = TypeVar("StateT")
FeedbackT = TypeVar("FeedbackT")

_SAFE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")


class StudyRunRecorder(LearningStudyObserver[StateT, FeedbackT], Generic[StateT, FeedbackT]):
    """Commit study receipts while leaving state and feedback meanings adapter-owned."""

    def __init__(
        self,
        *,
        root: Path,
        plan: CompiledLearningStudy,
        snapshot_state: Callable[[LearnerStateHandle[StateT]], Path],
        feedback_artifacts: Callable[[FeedbackHandle[FeedbackT]], tuple[ArtifactRef, ...]] | None = None,
        fault_injector: Callable[[str, PlannedArmRun | None, CompiledStudyStep | None], None] | None = None,
    ) -> None:
        self.root = Path(root).absolute()
        self.plan = plan
        self._snapshot_state = snapshot_state
        self._feedback_artifacts = feedback_artifacts or (lambda _feedback: ())
        self._fault_injector = fault_injector
        self._repository = ArtifactRepository(self.root / "_artifacts")
        self._trial_by_experience: dict[tuple[str, str], str] = {}
        self._feedback_by_step: dict[tuple[str, str], str] = {}
        mkdir_durable(self.root)
        _write_json_once(self.root / "study-spec.json", plan.spec.model_dump(mode="json", round_trip=True))
        _write_json_once(self.root / "study-plan.json", compiled_learning_study_to_data(plan))
        self._events = _read_events(self.root / "events.jsonl", plan.study_run_id)
        self._next_sequence = len(self._events)
        self._load_committed_indexes()
        if not self._events:
            self._append_event(StudyEventKind.STUDY_STARTED)

    def arm_started(self, arm_run: PlannedArmRun) -> None:
        self._append_event(StudyEventKind.ARM_RUN_STARTED, arm_run_id=arm_run.arm_run_id)

    def learner_initialised(self, arm_run: PlannedArmRun, state: LearnerStateHandle[StateT]) -> None:
        state_ref = self._publish_state(
            arm_run=arm_run,
            state=state,
            parent_state_id=None,
            created_after_step_id=None,
        )
        transition = LearnerTransitionReceipt(
            transition_id=f"{arm_run.arm_run_id}:transition:init",
            arm_run_id=arm_run.arm_run_id,
            step_id="__initialise__",
            operation_kind="initialise",
            state_before_id=None,
            candidate_state_id=state.state_id,
            committed_state_id=state.state_id,
            committed=True,
        )
        _write_model_once(self._state_path(state_ref.state_id), state_ref)
        _write_model_once(self._transition_path(transition.transition_id), transition)
        self._append_event(
            StudyEventKind.LEARNER_INITIALISED,
            arm_run_id=arm_run.arm_run_id,
            reference=_relative(self.root, self._state_path(state_ref.state_id)),
        )

    def step_started(self, arm_run: PlannedArmRun, step: CompiledStudyStep, step_index: int) -> None:
        mkdir_durable(self._stage_path(arm_run, step, step_index))
        self._append_event(
            StudyEventKind.STEP_STARTED,
            arm_run_id=arm_run.arm_run_id,
            step_id=step.step_id,
        )

    def step_committed(
        self,
        arm_run: PlannedArmRun,
        step: CompiledStudyStep,
        result: StepExecutionResult[FeedbackT],
        state_before: LearnerStateHandle[StateT],
        candidate_state: LearnerStateHandle[StateT],
        committed_state: LearnerStateHandle[StateT],
    ) -> None:
        state_ref = None
        if result.state_committed:
            state_ref = self._publish_state(
                arm_run=arm_run,
                state=committed_state,
                parent_state_id=state_before.state_id,
                created_after_step_id=step.step_id,
            )
        feedback_record = self._feedback_record(arm_run, step, result, state_before, committed_state)
        transition = self._transition_receipt(arm_run, step, result, state_before, candidate_state, committed_state)
        materialized_trial = None
        trial_payload = None
        if result.trial_record is not None:
            materialized_trial = materialize_trial_record(
                artifact_root=self.root / "ledger" / "_artifacts",
                record=result.trial_record,
            )
            trial_payload = {
                "record": materialized_trial.model_dump(mode="json", round_trip=True),
                "manifest": materialized_trial.run_manifest.model_dump(mode="json", round_trip=True),
            }
        receipt = StudyStepReceipt(
            study_run_id=self.plan.study_run_id,
            arm_run_id=arm_run.arm_run_id,
            step_id=step.step_id,
            step_index=result.step_index,
            step_kind=_receipt_step_kind(step),
            status=StudyStepStatus.COMPLETED,
            trial_id=None if materialized_trial is None else materialized_trial.trial_id,
            feedback_id=None if feedback_record is None else feedback_record.feedback_id,
            transition_id=transition.transition_id,
        )
        pending = {
            "state": None if state_ref is None else state_ref.model_dump(mode="json", round_trip=True),
            "feedback": None if feedback_record is None else feedback_record.model_dump(mode="json", round_trip=True),
            "transition": transition.model_dump(mode="json", round_trip=True),
            "receipt": receipt.model_dump(mode="json", round_trip=True),
            "trial": trial_payload,
        }
        stage_path = self._stage_path(arm_run, step, result.step_index)
        pending_path = stage_path / "pending.json"
        _write_json_once(pending_path, pending)
        self._fault("after_pending", arm_run, step)
        self._finish_pending(pending_path, arm_run=arm_run, step=step)

    def step_failed(
        self,
        arm_run: PlannedArmRun,
        step: CompiledStudyStep,
        result: StepExecutionResult[FeedbackT],
    ) -> None:
        if result.failure is None:
            raise LearningStudyPersistenceError("failed step has no failure evidence")
        receipt = StudyStepReceipt(
            study_run_id=self.plan.study_run_id,
            arm_run_id=arm_run.arm_run_id,
            step_id=step.step_id,
            step_index=result.step_index,
            step_kind=_receipt_step_kind(step),
            status=StudyStepStatus.FAILED,
            failure=StudyStepFailureRecord(category=result.failure.category, message=result.failure.message),
        )
        path = self._step_path(receipt.arm_run_id, receipt.step_index, receipt.step_id)
        _write_model_once(path, receipt)
        self._append_event(
            StudyEventKind.STEP_FAILED,
            arm_run_id=arm_run.arm_run_id,
            step_id=step.step_id,
            reference=_relative(self.root, path),
        )

    def arm_finished(self, result: ArmRunExecutionResult[FeedbackT]) -> None:
        kind = (
            StudyEventKind.ARM_RUN_COMPLETED
            if result.status is ArmRunStatus.COMPLETED
            else StudyEventKind.ARM_RUN_FAILED
        )
        self._append_event(kind, arm_run_id=result.arm_run_id)

    def study_finished(self, result: LearningStudyExecution[FeedbackT]) -> None:
        status = (
            StudyRunStatus.COMPLETED
            if all(item.status is ArmRunStatus.COMPLETED for item in result.arm_runs)
            else StudyRunStatus.COMPLETED_WITH_FAILED_ARMS
        )
        recorded = RecordedStudyExecution(
            study_run_id=result.study_run_id,
            status=status,
            arm_runs=tuple(
                RecordedArmRunResult(
                    arm_run_id=item.arm_run_id,
                    status=item.status.value,
                    initial_state_id=item.initial_state_id,
                    final_state_id=item.final_state_id,
                    trial_ids=tuple(record.trial_id for record in item.trial_records),
                )
                for item in result.arm_runs
            ),
        )
        _write_model_once(self.root / "result.json", recorded)
        if not any(event.kind is StudyEventKind.STUDY_COMPLETED for event in self._events):
            self._append_event(
                StudyEventKind.STUDY_COMPLETED,
                reference="result.json",
            )

    def study_cancelled(self) -> None:
        self._append_event(StudyEventKind.STUDY_CANCELLED)

    def finish_pending_transactions(self) -> None:
        """Complete callbacks that reached durable pending evidence before interruption."""

        for pending_path in sorted((self.root / "staging").glob("*/*/pending.json")):
            payload = _read_json_object(pending_path)
            receipt = StudyStepReceipt.model_validate(payload["receipt"])
            arm_run, step = self._planned_step(receipt.arm_run_id, receipt.step_index, receipt.step_id)
            final_path = self._step_path(receipt.arm_run_id, receipt.step_index, receipt.step_id)
            if final_path.is_file():
                self._remove_pending(pending_path)
                continue
            self._finish_pending(pending_path, arm_run=arm_run, step=step)

    def repair_missing_events(self) -> None:
        """Append receipt-derived events that were interrupted after authoritative commit."""

        existing = {(event.kind, event.reference) for event in self._events}
        for state_path in sorted((self.root / "states").glob("*.json")):
            state_ref = LearnerStateRef.model_validate_json(state_path.read_text(encoding="utf-8"))
            if state_ref.parent_state_id is not None:
                continue
            reference = _relative(self.root, state_path)
            key = (StudyEventKind.LEARNER_INITIALISED, reference)
            if key not in existing:
                self._append_event(
                    StudyEventKind.LEARNER_INITIALISED,
                    arm_run_id=state_ref.arm_run_id,
                    reference=reference,
                )
                existing.add(key)
        for arm_run in self.plan.arm_runs:
            for index, step in enumerate(arm_run.steps):
                path = self._step_path(arm_run.arm_run_id, index, step.step_id)
                if not path.is_file():
                    break
                receipt = StudyStepReceipt.model_validate_json(path.read_text(encoding="utf-8"))
                kind = (
                    StudyEventKind.STEP_COMMITTED
                    if receipt.status is StudyStepStatus.COMPLETED
                    else StudyEventKind.STEP_FAILED
                )
                reference = _relative(self.root, path)
                key = (kind, reference)
                if key not in existing:
                    self._append_event(
                        kind,
                        arm_run_id=arm_run.arm_run_id,
                        step_id=step.step_id,
                        reference=reference,
                    )
                    existing.add(key)

    def _finish_pending(
        self,
        pending_path: Path,
        *,
        arm_run: PlannedArmRun,
        step: CompiledStudyStep,
    ) -> None:
        payload = _read_json_object(pending_path)
        receipt = StudyStepReceipt.model_validate(payload["receipt"])
        trial_payload = payload.get("trial")
        if trial_payload is not None:
            trial = _trial_from_pending(trial_payload)
            self._write_trial_once(trial)
        self._fault("after_trial", arm_run, step)
        state_payload = payload.get("state")
        if state_payload is not None:
            state_ref = LearnerStateRef.model_validate(state_payload)
            self._repository.read_bytes(state_ref.artifact)
            _write_model_once(self._state_path(state_ref.state_id), state_ref)
        feedback_payload = payload.get("feedback")
        if feedback_payload is not None:
            feedback = FeedbackReleaseRecord.model_validate(feedback_payload)
            for reference in feedback.public_artifact_refs:
                self._repository.read_bytes(reference)
            _write_model_once(self._feedback_path(feedback.feedback_id), feedback)
        transition = LearnerTransitionReceipt.model_validate(payload["transition"])
        _write_model_once(self._transition_path(transition.transition_id), transition)
        self._fault("after_evidence", arm_run, step)
        receipt_path = self._step_path(receipt.arm_run_id, receipt.step_index, receipt.step_id)
        _write_model_once(receipt_path, receipt)
        self._fault("after_receipt", arm_run, step)
        self._fault("before_event", arm_run, step)
        self._append_event(
            StudyEventKind.STEP_COMMITTED,
            arm_run_id=receipt.arm_run_id,
            step_id=receipt.step_id,
            reference=_relative(self.root, receipt_path),
        )
        if isinstance(step, CompiledExperienceStep) and receipt.trial_id is not None:
            self._trial_by_experience[(arm_run.arm_run_id, step.experience_id)] = receipt.trial_id
        if isinstance(step, CompiledFeedbackStep) and receipt.feedback_id is not None:
            self._feedback_by_step[(arm_run.arm_run_id, step.step_id)] = receipt.feedback_id
        self._remove_pending(pending_path)

    def _publish_state(
        self,
        *,
        arm_run: PlannedArmRun,
        state: LearnerStateHandle[StateT],
        parent_state_id: str | None,
        created_after_step_id: str | None,
    ) -> LearnerStateRef:
        _component(state.state_id, "state")
        archive = _portable_state_archive(self._snapshot_state(state))
        artifact = self._repository.publish_bytes(data=archive, media_type="application/x-tar")
        return LearnerStateRef(
            state_id=state.state_id,
            arm_run_id=arm_run.arm_run_id,
            treatment_id=arm_run.treatment_id,
            parent_state_id=parent_state_id,
            created_after_step_id=created_after_step_id,
            artifact=artifact,
        )

    def _feedback_record(
        self,
        arm_run: PlannedArmRun,
        step: CompiledStudyStep,
        result: StepExecutionResult[FeedbackT],
        state_before: LearnerStateHandle[StateT],
        committed_state: LearnerStateHandle[StateT],
    ) -> FeedbackReleaseRecord | None:
        if not isinstance(step, CompiledFeedbackStep):
            return None
        if result.feedback is None:
            raise LearningStudyPersistenceError("feedback step did not return feedback evidence")
        source_trial_id = self._trial_by_experience.get((arm_run.arm_run_id, step.source_experience_id))
        if source_trial_id is None:
            raise LearningStudyPersistenceError("feedback source trial was not committed")
        references = self._feedback_artifacts(result.feedback)
        for reference in references:
            self._repository.read_bytes(reference)
        return FeedbackReleaseRecord(
            feedback_id=result.feedback.feedback_id,
            arm_run_id=arm_run.arm_run_id,
            release_step_id=step.step_id,
            source_experience_id=step.source_experience_id,
            source_trial_id=source_trial_id,
            view_id=step.feedback_view_id,
            public_artifact_refs=references,
            state_before_id=state_before.state_id,
            state_after_id=committed_state.state_id,
        )

    def _transition_receipt(
        self,
        arm_run: PlannedArmRun,
        step: CompiledStudyStep,
        result: StepExecutionResult[FeedbackT],
        state_before: LearnerStateHandle[StateT],
        candidate_state: LearnerStateHandle[StateT],
        committed_state: LearnerStateHandle[StateT],
    ) -> LearnerTransitionReceipt:
        if isinstance(step, CompiledExperienceStep):
            operation_kind: Literal[
                "initialise",
                "experience",
                "feedback_release",
                "consolidation",
                "probe_discard",
            ] = "experience" if result.state_committed else "probe_discard"
            feedback_ids: tuple[str, ...] = ()
        elif isinstance(step, CompiledFeedbackStep):
            operation_kind = "feedback_release"
            feedback_ids = () if result.feedback is None else (result.feedback.feedback_id,)
        elif isinstance(step, CompiledConsolidationStep):
            operation_kind = "consolidation"
            try:
                feedback_ids = tuple(
                    self._feedback_by_step[(arm_run.arm_run_id, feedback_step_id)]
                    for feedback_step_id in step.feedback_step_ids
                )
            except KeyError as error:
                raise LearningStudyPersistenceError("consolidation feedback was not committed") from error
        else:  # pragma: no cover
            raise TypeError(type(step).__name__)
        return LearnerTransitionReceipt(
            transition_id=f"{arm_run.arm_run_id}:transition:{result.step_index + 1:03d}",
            arm_run_id=arm_run.arm_run_id,
            step_id=step.step_id,
            operation_kind=operation_kind,
            state_before_id=state_before.state_id,
            candidate_state_id=candidate_state.state_id,
            committed_state_id=committed_state.state_id,
            committed=bool(result.state_committed),
            feedback_ids=feedback_ids,
        )

    def _write_trial_once(self, trial: TrialRecord) -> None:
        try:
            write_trial_record(ledger_root=self.root / "ledger", record=trial)
        except DuplicateTrialRecordError as error:
            path = self._trial_path(trial.experiment_id, trial.trial_id)
            existing = read_trial_record(path, ledger_root=self.root / "ledger")
            if existing.model_dump(mode="json", round_trip=True) != trial.model_dump(mode="json", round_trip=True):
                raise LearningStudyPersistenceError(
                    f"trial record conflicts with committed bytes: {trial.trial_id}"
                ) from error

    def _load_committed_indexes(self) -> None:
        for arm_run in self.plan.arm_runs:
            for index, step in enumerate(arm_run.steps):
                receipt_path = self._step_path(arm_run.arm_run_id, index, step.step_id)
                if not receipt_path.is_file():
                    break
                receipt = StudyStepReceipt.model_validate_json(receipt_path.read_text(encoding="utf-8"))
                if isinstance(step, CompiledExperienceStep) and receipt.trial_id is not None:
                    self._trial_by_experience[(arm_run.arm_run_id, step.experience_id)] = receipt.trial_id
                if isinstance(step, CompiledFeedbackStep) and receipt.feedback_id is not None:
                    self._feedback_by_step[(arm_run.arm_run_id, step.step_id)] = receipt.feedback_id

    def _append_event(
        self,
        kind: StudyEventKind,
        *,
        arm_run_id: str | None = None,
        step_id: str | None = None,
        reference: str | None = None,
    ) -> None:
        event = StudyEvent(
            sequence=self._next_sequence,
            study_run_id=self.plan.study_run_id,
            kind=kind,
            arm_run_id=arm_run_id,
            step_id=step_id,
            reference=reference,
        )
        path = self.root / "events.jsonl"
        mkdir_durable(path.parent)
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            payload = _json_bytes(event.model_dump(mode="json", round_trip=True))
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        fsync_directory(path.parent)
        self._events.append(event)
        self._next_sequence += 1

    def _planned_step(self, arm_run_id: str, step_index: int, step_id: str) -> tuple[PlannedArmRun, CompiledStudyStep]:
        arm_run = next((item for item in self.plan.arm_runs if item.arm_run_id == arm_run_id), None)
        if arm_run is None or step_index >= len(arm_run.steps):
            raise LearningStudyPersistenceError("pending transaction does not match the compiled plan")
        step = arm_run.steps[step_index]
        if step.step_id != step_id:
            raise LearningStudyPersistenceError("pending step identity does not match the compiled plan")
        return arm_run, step

    def _state_path(self, state_id: str) -> Path:
        return self.root / "states" / f"{_component(state_id, 'state')}.json"

    def _transition_path(self, transition_id: str) -> Path:
        return self.root / "transitions" / f"{_component(transition_id, 'transition')}.json"

    def _feedback_path(self, feedback_id: str) -> Path:
        return self.root / "feedback" / f"{_component(feedback_id, 'feedback')}.json"

    def _step_path(self, arm_run_id: str, step_index: int, step_id: str) -> Path:
        return (
            self.root
            / "steps"
            / _component(arm_run_id, "arm run")
            / f"{step_index:03d}-{_component(step_id, 'step')}.json"
        )

    def _stage_path(self, arm_run: PlannedArmRun, step: CompiledStudyStep, step_index: int) -> Path:
        return (
            self.root
            / "staging"
            / _component(arm_run.arm_run_id, "arm run")
            / f"{step_index:03d}-{_component(step.step_id, 'step')}"
        )

    def _trial_path(self, experiment_id: str, trial_id: str) -> Path:
        return self.root / "ledger" / experiment_id / f"{trial_id}.json"

    def _fault(self, point: str, arm_run: PlannedArmRun, step: CompiledStudyStep) -> None:
        if self._fault_injector is not None:
            self._fault_injector(point, arm_run, step)

    @staticmethod
    def _remove_pending(pending_path: Path) -> None:
        pending_path.unlink(missing_ok=True)
        try:
            pending_path.parent.rmdir()
        except OSError:
            pass


def create_study_run(
    *,
    root: Path,
    plan: CompiledLearningStudy,
    snapshot_state: Callable[[LearnerStateHandle[StateT]], Path],
    feedback_artifacts: Callable[[FeedbackHandle[FeedbackT]], tuple[ArtifactRef, ...]] | None = None,
    fault_injector: Callable[[str, PlannedArmRun | None, CompiledStudyStep | None], None] | None = None,
) -> StudyRunRecorder[StateT, FeedbackT]:
    return StudyRunRecorder(
        root=root,
        plan=plan,
        snapshot_state=snapshot_state,
        feedback_artifacts=feedback_artifacts,
        fault_injector=fault_injector,
    )


def _portable_state_archive(root: Path) -> bytes:
    selected_root = Path(root).absolute()
    if not selected_root.is_dir() or selected_root.is_symlink():
        raise LearningStudyPersistenceError("learner snapshot root must be a real directory")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(selected_root.rglob("*"), key=lambda item: item.relative_to(selected_root).as_posix()):
            relative = path.relative_to(selected_root)
            if path.is_symlink():
                raise LearningStudyPersistenceError(f"learner snapshot contains a symlink: {relative}")
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(selected_root.resolve(strict=True)):
                raise LearningStudyPersistenceError(f"learner snapshot escapes its root: {relative}")
            if not path.is_dir() and not path.is_file():
                raise LearningStudyPersistenceError(f"learner snapshot contains a special file: {relative}")
            info = tarfile.TarInfo(relative.as_posix() + ("/" if path.is_dir() else ""))
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            info.mode = 0o755 if path.is_dir() else 0o644
            if path.is_file():
                payload = path.read_bytes()
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            else:
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
    return buffer.getvalue()


def _trial_from_pending(value: object) -> TrialRecord:
    if not isinstance(value, dict):
        raise LearningStudyPersistenceError("pending trial evidence must be an object")
    record = TrialRecord.model_validate(value.get("record"))
    manifest = RunManifest.model_validate(value.get("manifest"))
    return record.bind_run_manifest(manifest)


def _receipt_step_kind(
    step: CompiledStudyStep,
) -> Literal["run_experience", "release_feedback", "consolidate"]:
    if isinstance(step, CompiledExperienceStep):
        return "run_experience"
    if isinstance(step, CompiledFeedbackStep):
        return "release_feedback"
    return "consolidate"


def _read_events(path: Path, study_run_id: str) -> list[StudyEvent]:
    if not path.exists():
        return []
    events: list[StudyEvent] = []
    with path.open(encoding="utf-8") as stream:
        for sequence, line in enumerate(stream):
            if not line.strip():
                raise LearningStudyPersistenceError("study event log contains a blank entry")
            event = StudyEvent.model_validate_json(line)
            if event.sequence != sequence or event.study_run_id != study_run_id:
                raise LearningStudyPersistenceError("study event sequence or run identity is corrupt")
            events.append(event)
    return events


def _write_model_once(path: Path, value: Any) -> None:
    _write_json_once(path, value.model_dump(mode="json", round_trip=True))


def _write_json_once(path: Path, value: object) -> None:
    payload = _json_bytes(value)
    if path.exists():
        if path.read_bytes() != payload:
            raise LearningStudyPersistenceError(f"immutable study evidence conflicts at {path}")
        return
    mkdir_durable(path.parent)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            if path.read_bytes() != payload:
                raise LearningStudyPersistenceError(f"immutable study evidence conflicts at {path}") from error
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LearningStudyPersistenceError(f"study evidence must contain an object: {path}")
    return value


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _component(value: str, label: str) -> str:
    if not _SAFE_COMPONENT.fullmatch(value):
        raise LearningStudyPersistenceError(f"{label} id is not safe for persisted evidence: {value!r}")
    return value


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


__all__ = ("StudyRunRecorder", "create_study_run")
