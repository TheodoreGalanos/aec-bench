# ABOUTME: Provides the scheduler-facing finite lifecycle trial adapter.
# ABOUTME: Binds lifecycle-owned execution and evidence retention to one operational attempt.

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from aec_bench.contracts.identity import (
    EntityKey,
    EntityKind,
    PortableRelativePath,
    new_entity_id,
    validate_uuidv7,
)
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan, SingleAttemptRecipe
from aec_bench.contracts.trial_record import ExecutionStatus, TrialRecord
from aec_bench.execution.models import (
    AttemptProcessStatus,
    AttemptReceipt,
    AttemptResourceUsage,
    CancellationStatus,
    FailureClass,
    FailureClassification,
    FailureKind,
    FinalizationState,
    ReconciliationState,
    TrialFinalization,
    WorkerOutcome,
)
from aec_bench.execution.operational import AttemptRecord, OperationalStore, WorkItemRecord
from aec_bench.ledger.evidence_run_store import EvidenceRunStore
from aec_bench.ledger.writer import (
    DuplicateAppendOnlyFileError,
    DuplicateTrialRecordError,
    write_append_only_json_at,
    write_trial_record_at,
)
from aec_bench.lifecycles.application import (
    LifecycleEvidenceRetention,
    LifecycleTrialExecutor,
    LifecycleVerifier,
    run_lifecycle_trial,
    validate_lifecycle_release,
)
from aec_bench.lifecycles.finalization import live_lifecycle_finalization_source
from aec_bench.lifecycles.values import LifecycleTrial
from aec_bench.trials import planned_trial_binding, validate_planned_trial_record


class LifecycleTrialAdapterError(RuntimeError):
    """Raised when a scheduled lifecycle trial cannot be bound or published safely."""


class LifecycleTrialAdapter:
    """Run one exact finite lifecycle through the existing lifecycle application path."""

    def __init__(
        self,
        *,
        evidence_store: EvidenceRunStore,
        operational_store: OperationalStore,
        plan: RunPlan,
        trials: Sequence[LifecycleTrial],
        execute: LifecycleTrialExecutor,
        verify: LifecycleVerifier,
        retain: LifecycleEvidenceRetention = live_lifecycle_finalization_source,
    ) -> None:
        self._evidence_store = evidence_store
        self._operational_store = operational_store
        self._plan = plan
        self._trials = self._index_trials(trials)
        self._execute = execute
        self._verify = verify
        self._retain = retain

    def __call__(self, work_item: WorkItemRecord, attempt: AttemptRecord) -> WorkerOutcome:
        """Execute one complete lifecycle attempt and return its strict outcome."""

        return self.execute(work_item, attempt).outcome

    def execute(self, work_item: WorkItemRecord, attempt: AttemptRecord) -> LifecycleTrialExecution:
        """Bind scheduler identities, invoke lifecycle execution, and publish its portable result."""

        stored = self._evidence_store.read_run(self._plan.run_identity)
        if stored.plan != self._plan or stored.plan is None:
            raise LifecycleTrialAdapterError("authoritative run plan does not match the persisted plan")
        if stored.state.state not in {"ready", "started"}:
            raise LifecycleTrialAdapterError("lifecycle execution requires a ready or started evidence run")
        planned = self._planned_trial(work_item)
        self._validate_attempt(work_item, attempt)
        lifecycle = self._trials.get(str(planned.trial_identity.id))
        if lifecycle is None:
            raise LifecycleTrialAdapterError(
                f"planned lifecycle trial has no supplied trial: {planned.trial_identity.id}"
            )
        try:
            validate_lifecycle_release(planned, lifecycle, stored.spec)
        except ValueError as error:
            raise LifecycleTrialAdapterError(str(error)) from error
        record_path = self._record_path(planned)
        finalization_path = self._finalization_path(planned)
        if record_path.exists() or finalization_path.exists():
            raise LifecycleTrialAdapterError(f"trial finalization already exists: {planned.trial_identity.id}")
        if stored.state.state == "ready":
            self._evidence_store.start_run(
                self._plan.run_identity,
                started_at=attempt.started_at or attempt.created_at,
            )

        started_at = attempt.started_at or attempt.created_at
        submission_id = str(new_entity_id(EntityKind.BACKEND_SUBMISSION))
        self._operational_store.record_backend_submission(
            submission_id,
            attempt_id=attempt.attempt_id,
            backend=work_item.backend,
            now=started_at,
        )
        self._operational_store.transition_backend_submission(submission_id, state="running", now=started_at)
        binding = planned_trial_binding(planned, stored.spec)
        try:
            record = run_lifecycle_trial(
                trial=lifecycle,
                execute=self._execute,
                verify=self._verify,
                retain=self._retain,
                planned_trial_binding=binding,
            )
            validate_planned_trial_record(
                record,
                planned,
                stored.spec,
                task_revision=lifecycle.compiled.envelope.package_sha256,
            )
        except Exception as error:
            finished_at = datetime.now(UTC)
            self._mark_failed(attempt, submission_id, finished_at)
            self._persist_receipt(
                self._failure_receipt(work_item, attempt, planned, submission_id, started_at, finished_at, error)
            )
            raise

        finished_at = record.completed_at or datetime.now(UTC)
        succeeded = record.execution_status is ExecutionStatus.COMPLETED
        receipt_published = False
        try:
            write_trial_record_at(path=record_path, record=record)
            receipt = self._receipt_from_record(
                work_item, attempt, planned, submission_id, record, started_at, finished_at
            )
            self._persist_receipt(receipt)
            receipt_published = True
            finalization = TrialFinalization(
                finalization_id=new_entity_id(EntityKind.RECEIPT),
                trial_id=planned.trial_id,
                attempt_id=validate_uuidv7(attempt.attempt_id),
                record_version=1,
                trial_record_ref=PortableRelativePath(record_path.relative_to(self._evidence_store.root).as_posix()),
                published_at=finished_at,
                state=FinalizationState.CURRENT,
            )
            write_append_only_json_at(path=finalization_path, payload=finalization.model_dump_json(indent=2) + "\n")
        except Exception as error:
            failed_at = datetime.now(UTC)
            self._mark_failed(attempt, submission_id, failed_at)
            if not receipt_published:
                self._persist_receipt(
                    self._failure_receipt(work_item, attempt, planned, submission_id, started_at, failed_at, error)
                )
            if isinstance(error, DuplicateAppendOnlyFileError | DuplicateTrialRecordError):
                raise LifecycleTrialAdapterError(
                    f"trial finalization already exists: {planned.trial_identity.id}"
                ) from error
            raise
        self._operational_store.transition_attempt(
            attempt.attempt_id,
            state="succeeded" if succeeded else "failed",
            now=finished_at,
        )
        self._operational_store.transition_backend_submission(
            submission_id,
            state="completed" if succeeded else "failed",
            now=finished_at,
        )
        return LifecycleTrialExecution(record=record, receipt=receipt, finalization=finalization)

    @staticmethod
    def _index_trials(trials: Sequence[LifecycleTrial]) -> dict[str, LifecycleTrial]:
        indexed: dict[str, LifecycleTrial] = {}
        for trial in trials:
            trial_id = trial.planned.trial_id
            if trial_id in indexed:
                raise LifecycleTrialAdapterError(f"lifecycle trials must have unique trial IDs: {trial_id}")
            indexed[trial_id] = trial
        return indexed

    def _planned_trial(self, work_item: WorkItemRecord) -> PlannedTrial:
        if work_item.run_id != str(self._plan.run_id) or work_item.plan_id != str(self._plan.plan_id):
            raise LifecycleTrialAdapterError("work item does not belong to the authoritative run plan")
        matches = [trial for trial in self._plan.trials if str(trial.trial_id) == work_item.trial_id]
        if len(matches) != 1:
            raise LifecycleTrialAdapterError(f"work item does not identify one planned trial: {work_item.trial_id}")
        planned = matches[0]
        if planned.execution_family != "lifecycle":
            raise LifecycleTrialAdapterError("scheduled work item is not a lifecycle trial")
        if planned.ordinal != work_item.ordinal:
            raise LifecycleTrialAdapterError("work item ordinal does not match the authoritative trial")
        if planned.compute.backend != work_item.backend:
            raise LifecycleTrialAdapterError("work item backend does not match the authoritative trial")
        if not isinstance(planned.attempt_recipe, SingleAttemptRecipe):
            raise LifecycleTrialAdapterError("lifecycle trials require the single_attempt recipe")
        return planned

    @staticmethod
    def _validate_attempt(work_item: WorkItemRecord, attempt: AttemptRecord) -> None:
        if work_item.state != "running":
            raise LifecycleTrialAdapterError("lifecycle execution requires a running scheduler work item")
        if attempt.work_id != work_item.work_id or attempt.trial_id != work_item.trial_id:
            raise LifecycleTrialAdapterError("scheduler attempt does not match the work item")
        if attempt.run_id != work_item.run_id:
            raise LifecycleTrialAdapterError("scheduler attempt does not match the work item run")
        if attempt.lease_id is None:
            raise LifecycleTrialAdapterError("lifecycle execution requires a lease-bound attempt")
        if attempt.state != "running":
            raise LifecycleTrialAdapterError("lifecycle execution requires a running scheduler attempt")
        if attempt.candidate_index != 1:
            raise LifecycleTrialAdapterError("lifecycle execution requires candidate 1")

    def _record_path(self, planned: PlannedTrial) -> Path:
        return (
            self._evidence_store.run_directory(self._plan.run_identity) / "trial-records" / f"{planned.trial_id}.json"
        )

    def _finalization_path(self, planned: PlannedTrial) -> Path:
        return (
            self._evidence_store.run_directory(self._plan.run_identity) / "finalizations" / f"{planned.trial_id}.json"
        )

    def _persist_receipt(self, receipt: AttemptReceipt) -> None:
        path = self._evidence_store.run_directory(self._plan.run_identity) / "receipts" / f"{receipt.receipt_id}.json"
        try:
            write_append_only_json_at(path=path, payload=receipt.model_dump_json(indent=2) + "\n")
        except DuplicateAppendOnlyFileError as error:
            raise LifecycleTrialAdapterError(f"attempt receipt already exists: {receipt.receipt_id}") from error

    def _mark_failed(self, attempt: AttemptRecord, submission_id: str, now: datetime) -> None:
        self._operational_store.transition_attempt(attempt.attempt_id, state="failed", now=now)
        self._operational_store.transition_backend_submission(submission_id, state="failed", now=now)

    @staticmethod
    def _failure_receipt(
        work_item: WorkItemRecord,
        attempt: AttemptRecord,
        planned: PlannedTrial,
        submission_id: str,
        started_at: datetime,
        finished_at: datetime,
        error: Exception,
    ) -> AttemptReceipt:
        return AttemptReceipt(
            receipt_id=new_entity_id(EntityKind.RECEIPT),
            receipt_key=EntityKey(f"{work_item.work_key}/attempt-{attempt.attempt_number}"),
            attempt_id=validate_uuidv7(attempt.attempt_id),
            backend=work_item.backend,
            submission_id=validate_uuidv7(submission_id),
            requested_condition=planned.agent_condition.identity,
            started_at=started_at,
            finished_at=finished_at,
            process_status=AttemptProcessStatus.FAILED,
            cancellation_status=CancellationStatus.NOT_REQUESTED,
            resource_usage=AttemptResourceUsage(wall_seconds=max(0.0, (finished_at - started_at).total_seconds())),
            failure=FailureClassification(
                failure_class=FailureClass.INFRASTRUCTURE,
                kind=FailureKind.RESULT_IMPORT_FAILED,
                message=str(error) or "lifecycle execution failed",
            ),
            reconciliation_status=ReconciliationState.NOT_REQUIRED,
        )

    @staticmethod
    def _receipt_from_record(
        work_item: WorkItemRecord,
        attempt: AttemptRecord,
        planned: PlannedTrial,
        submission_id: str,
        record: TrialRecord,
        started_at: datetime,
        finished_at: datetime,
    ) -> AttemptReceipt:
        output_references = () if record.output is None else tuple(item.artifact for item in record.output.artifacts)
        succeeded = record.execution_status is ExecutionStatus.COMPLETED
        return AttemptReceipt(
            receipt_id=new_entity_id(EntityKind.RECEIPT),
            receipt_key=EntityKey(f"{work_item.work_key}/attempt-{attempt.attempt_number}"),
            attempt_id=validate_uuidv7(attempt.attempt_id),
            backend=work_item.backend,
            submission_id=validate_uuidv7(submission_id),
            requested_condition=planned.agent_condition.identity,
            started_at=started_at,
            finished_at=finished_at,
            process_status=AttemptProcessStatus.SUCCEEDED if succeeded else AttemptProcessStatus.FAILED,
            cancellation_status=CancellationStatus.NOT_REQUESTED,
            resource_usage=AttemptResourceUsage(wall_seconds=max(0.0, (finished_at - started_at).total_seconds())),
            output_references=output_references,
            authority_evidence=record.authority_evidence,
            failure=(
                None
                if succeeded
                else FailureClassification(
                    failure_class=FailureClass.BENCHMARK,
                    kind=FailureKind.TASK_FAILURE,
                    message="lifecycle execution did not complete",
                )
            ),
            reconciliation_status=ReconciliationState.NOT_REQUIRED,
        )


@dataclass(frozen=True, slots=True)
class LifecycleTrialExecution:
    """Portable lifecycle record, attempt receipt, and finalization."""

    record: TrialRecord
    receipt: AttemptReceipt
    finalization: TrialFinalization

    @property
    def outcome(self) -> WorkerOutcome:
        return WorkerOutcome(
            terminal_state="succeeded" if self.record.execution_status is ExecutionStatus.COMPLETED else "failed",
            receipts=(self.receipt,),
            finalization=self.finalization,
        )


__all__ = ("LifecycleTrialAdapter", "LifecycleTrialAdapterError", "LifecycleTrialExecution")
