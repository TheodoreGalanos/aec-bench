# ABOUTME: Provides the strict scheduler-facing Harbor backend adapter.
# ABOUTME: Binds remote Harbor transport state to canonical attempts and portable trial evidence.

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, cast
from uuid import UUID

from pydantic import PositiveInt, field_validator

from aec_bench.contracts.identity import (
    EntityKey,
    EntityKind,
    PortableRelativePath,
    new_entity_id,
    validate_uuidv7,
)
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import PlannedTrial, RunPlan, SingleAttemptRecipe
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef, RepositoryTaskSnapshotRef
from aec_bench.contracts.trial_record import ExecutionStatus, TrialRecord
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.execution.models import (
    AttemptProcessStatus,
    AttemptReceipt,
    AttemptResourceUsage,
    BackendCancellationResult,
    CancellationStatus,
    FailureClass,
    FailureClassification,
    FailureKind,
    FinalizationState,
    ReconciliationState,
    TrialFinalization,
    WorkerOutcome,
)
from aec_bench.execution.operational import (
    AttemptRecord,
    BackendSubmissionRecord,
    OperationalStore,
    OperationalStoreError,
    WorkItemRecord,
)
from aec_bench.harness.harbor_reconciliation import HarborTrialTransport, reconcile_harbor_trial_records
from aec_bench.ledger.evidence_run_store import EvidenceRunStore
from aec_bench.ledger.reader import read_trial_record
from aec_bench.ledger.writer import (
    DuplicateAppendOnlyFileError,
    DuplicateTrialRecordError,
    materialize_trial_record,
    write_append_only_json_at,
    write_trial_record_at,
)
from aec_bench.trials import validate_planned_trial_record


class HarborBackendError(RuntimeError):
    """Raised when Harbor cannot be bound to or reconciled with one planned attempt."""


class HarborRemoteState(FrozenStrictModel):
    """One observed Harbor state returned by an injected backend client."""

    state: Literal["submitted", "running", "completed", "failed", "unknown"]


class HarborSubmission(FrozenStrictModel):
    """Provider identifiers returned after Harbor accepts one submission."""

    external_id: NonEmptyStr
    harbor_trial_name: NonEmptyStr


class HarborAttemptTransport(FrozenStrictModel):
    """Strict mapping between one AEC-Bench attempt and one Harbor trial."""

    schema_version: Literal[1] = 1
    run_id: UUID
    plan_id: UUID
    trial_id: UUID
    work_id: UUID
    attempt_id: UUID
    submission_id: UUID
    ordinal: PositiveInt
    harbor_job_name: NonEmptyStr
    harbor_trial_name: NonEmptyStr | None = None

    @field_validator("run_id", "plan_id", "trial_id", "work_id", "attempt_id", "submission_id", mode="before")
    @classmethod
    def validate_ids(cls, value: UUID | str) -> UUID:
        return validate_uuidv7(value)

    @field_validator("harbor_job_name")
    @classmethod
    def validate_harbor_job_name(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) is None:
            raise ValueError("Harbor job names must be safe single path components")
        return value


class HarborBackendClient(Protocol):
    """Minimal fakeable Harbor transport boundary."""

    def submit(self, transport: HarborAttemptTransport) -> HarborSubmission: ...

    def inspect(self, submission: HarborSubmission) -> HarborRemoteState: ...

    def collect(self, submission: HarborSubmission) -> TrialRecord | None: ...


class HarborBackend:
    """Run and reconcile one exact scheduler-owned Harbor attempt."""

    capabilities = frozenset({"submit", "inspect", "collect", "cancel", "reconcile"})

    def __init__(
        self,
        *,
        evidence_store: EvidenceRunStore,
        operational_store: OperationalStore,
        plan: RunPlan,
        client: HarborBackendClient,
    ) -> None:
        self._evidence_store = evidence_store
        self._operational_store = operational_store
        self._plan = plan
        self._client = client

    def __call__(self, work_item: WorkItemRecord, attempt: AttemptRecord) -> WorkerOutcome:
        return self.execute(work_item, attempt)

    def execute(self, work_item: WorkItemRecord, attempt: AttemptRecord) -> WorkerOutcome:
        stored = self._evidence_store.read_run(self._plan.run_identity)
        if stored.plan != self._plan or stored.plan is None:
            raise HarborBackendError("authoritative run plan does not match the persisted plan")
        if stored.state.state not in {"ready", "started"}:
            raise HarborBackendError("Harbor execution requires a ready or started evidence run")
        planned = self._planned_trial(work_item)
        self._validate_attempt(work_item, attempt)
        if not isinstance(planned.attempt_recipe, SingleAttemptRecipe):
            raise HarborBackendError("Harbor supports only the single_attempt recipe")
        if stored.state.state == "ready":
            self._evidence_store.start_run(
                self._plan.run_identity,
                started_at=attempt.started_at or attempt.created_at,
            )
        if self._operational_store.list_backend_submissions(attempt.attempt_id):
            raise HarborBackendError("Harbor attempt already has a backend submission")
        record_path = self._record_path(planned)
        finalization_path = self._finalization_path(planned)
        if record_path.exists() or finalization_path.exists():
            raise HarborBackendError(f"trial finalization already exists: {planned.trial_id}")

        submission_id = new_entity_id(EntityKind.BACKEND_SUBMISSION)
        started_at = attempt.started_at or attempt.created_at
        self._operational_store.record_backend_submission(
            submission_id,
            attempt_id=attempt.attempt_id,
            backend=work_item.backend,
            now=started_at,
        )
        transport = HarborAttemptTransport(
            run_id=self._plan.run_id,
            plan_id=self._plan.plan_id,
            trial_id=planned.trial_id,
            work_id=validate_uuidv7(work_item.work_id),
            attempt_id=validate_uuidv7(attempt.attempt_id),
            submission_id=submission_id,
            ordinal=planned.ordinal,
            harbor_job_name=f"aec-planned-{planned.trial_id.hex}",
        )
        try:
            self._persist_transport(transport)
            try:
                submission = self._client.submit(transport)
            except Exception:
                return self._unknown_outcome(work_item, attempt, planned, submission_id, started_at)
            self._operational_store.bind_backend_submission_external_ids(
                submission_id,
                external_id=submission.external_id,
                external_work_id=submission.harbor_trial_name,
                now=datetime.now(UTC),
            )
            self._operational_store.transition_backend_submission(
                submission_id,
                state="running",
                now=datetime.now(UTC),
            )
            try:
                observed = self._client.inspect(submission)
            except Exception:
                return self._unknown_outcome(work_item, attempt, planned, submission_id, started_at)
            if observed.state == "unknown":
                return self._unknown_outcome(work_item, attempt, planned, submission_id, started_at)
            if observed.state not in {"completed", "failed"}:
                return self._unknown_outcome(work_item, attempt, planned, submission_id, started_at)
            try:
                record = self._client.collect(submission)
            except Exception:
                return self._unknown_outcome(work_item, attempt, planned, submission_id, started_at)
            if record is None:
                return self._unknown_outcome(work_item, attempt, planned, submission_id, started_at)
            canonical = self._canonical_record(
                record,
                planned,
                stored.spec,
                harbor_trial_name=submission.harbor_trial_name,
                external_id=submission.external_id,
            )
            return self._publish_result(
                work_item=work_item,
                attempt=attempt,
                planned=planned,
                submission_id=submission_id,
                record=canonical,
                started_at=started_at,
                process_failed=observed.state == "failed",
                record_path=record_path,
                finalization_path=finalization_path,
            )
        except Exception as error:
            finished_at = datetime.now(UTC)
            self._operational_store.transition_attempt(attempt.attempt_id, state="failed", now=finished_at)
            self._operational_store.transition_backend_submission(submission_id, state="failed", now=finished_at)
            raise HarborBackendError(str(error)) from error

    def cancel(
        self, work_item: WorkItemRecord, attempt: AttemptRecord, submission: BackendSubmissionRecord
    ) -> BackendCancellationResult:
        """Request cancellation for one accepted Harbor submission."""

        if submission.external_id is None:
            return BackendCancellationResult(status="unknown", message="Harbor submission has no external ID")
        cancel = getattr(self._client, "cancel", None)
        if not callable(cancel):
            return BackendCancellationResult(
                status="unsupported", message="Harbor client does not support cancellation"
            )
        if submission.external_work_id is None:
            return BackendCancellationResult(status="unknown", message="Harbor submission has no trial ID")
        harbor_submission = HarborSubmission(
            external_id=submission.external_id,
            harbor_trial_name=submission.external_work_id,
        )
        try:
            cancel_call = cast(Callable[[HarborSubmission], BackendCancellationResult], cancel)
            return cancel_call(harbor_submission)
        except Exception as error:
            return BackendCancellationResult(
                status="unknown", message=f"Harbor cancellation status is unknown: {error}"
            )

    def reconcile(
        self, work_item: WorkItemRecord, attempt: AttemptRecord, submission: BackendSubmissionRecord
    ) -> WorkerOutcome:
        """Inspect and collect one previously uncertain Harbor attempt."""

        stored = self._evidence_store.read_run(self._plan.run_identity)
        planned = self._planned_trial(work_item)
        self._validate_attempt(work_item, attempt, allow_reconciliation=True)
        published = self._existing_published_outcome(attempt, planned, submission, stored.spec)
        if published is not None:
            return published
        if submission.external_id is None or submission.external_work_id is None:
            return self._existing_unknown_outcome(work_item, attempt, planned, UUID(submission.submission_id))
        harbor_submission = HarborSubmission(
            external_id=submission.external_id,
            harbor_trial_name=submission.external_work_id,
        )
        try:
            observed = self._client.inspect(harbor_submission)
        except Exception:
            return self._existing_unknown_outcome(work_item, attempt, planned, UUID(submission.submission_id))
        if observed.state not in {"completed", "failed"}:
            return self._existing_unknown_outcome(work_item, attempt, planned, UUID(submission.submission_id))
        try:
            record = self._client.collect(harbor_submission)
        except Exception:
            return self._existing_unknown_outcome(work_item, attempt, planned, UUID(submission.submission_id))
        if record is None:
            return self._existing_unknown_outcome(work_item, attempt, planned, UUID(submission.submission_id))
        canonical = self._canonical_record(
            record,
            planned,
            stored.spec,
            harbor_trial_name=harbor_submission.harbor_trial_name,
            external_id=submission.external_id,
        )
        return self._publish_result(
            work_item=work_item,
            attempt=attempt,
            planned=planned,
            submission_id=UUID(submission.submission_id),
            record=canonical,
            started_at=attempt.started_at or attempt.created_at,
            process_failed=observed.state == "failed",
            record_path=self._record_path(planned),
            finalization_path=self._finalization_path(planned),
        )

    def _publish_result(
        self,
        *,
        work_item: WorkItemRecord,
        attempt: AttemptRecord,
        planned: PlannedTrial,
        submission_id: UUID,
        record: TrialRecord,
        started_at: datetime,
        process_failed: bool,
        record_path: Path,
        finalization_path: Path,
    ) -> WorkerOutcome:
        finished_at = record.completed_at or datetime.now(UTC)
        process_succeeded = not process_failed and record.execution_status is ExecutionStatus.COMPLETED
        record = materialize_trial_record(
            artifact_root=record_path.parent / "_artifacts",
            record=record,
        )
        receipt = self._receipt(
            work_item=work_item,
            attempt=attempt,
            planned=planned,
            submission_id=submission_id,
            record=record,
            started_at=started_at,
            finished_at=finished_at,
            succeeded=process_succeeded,
        )
        try:
            write_trial_record_at(path=record_path, record=record)
            self._persist_receipt(receipt)
            finalization = TrialFinalization(
                finalization_id=new_entity_id(EntityKind.RECEIPT),
                trial_id=planned.trial_id,
                attempt_id=validate_uuidv7(attempt.attempt_id),
                record_version=1,
                trial_record_ref=PortableRelativePath(record_path.relative_to(self._evidence_store.root).as_posix()),
                published_at=finished_at,
                state=FinalizationState.CURRENT,
            )
            write_append_only_json_at(
                path=finalization_path,
                payload=finalization.model_dump_json(indent=2) + "\n",
            )
        except (DuplicateTrialRecordError, DuplicateAppendOnlyFileError) as error:
            self._mark_failed(attempt, submission_id)
            raise HarborBackendError(f"trial finalization already exists: {planned.trial_id}") from error
        except Exception:
            self._mark_failed(attempt, submission_id)
            raise
        self._operational_store.transition_attempt(
            attempt.attempt_id,
            state="failed" if not process_succeeded else "succeeded",
            now=finished_at,
        )
        self._operational_store.transition_backend_submission(
            submission_id,
            state="failed" if not process_succeeded else "completed",
            now=finished_at,
        )
        return WorkerOutcome(
            terminal_state="failed" if not process_succeeded else "succeeded",
            receipts=(receipt,),
            finalization=finalization,
        )

    def _unknown_outcome(
        self,
        work_item: WorkItemRecord,
        attempt: AttemptRecord,
        planned: PlannedTrial,
        submission_id: UUID,
        started_at: datetime,
    ) -> WorkerOutcome:
        finished_at = datetime.now(UTC)
        receipt = AttemptReceipt(
            receipt_id=new_entity_id(EntityKind.RECEIPT),
            receipt_key=EntityKey(f"{work_item.work_key}/attempt-{attempt.attempt_number}"),
            attempt_id=validate_uuidv7(attempt.attempt_id),
            backend=work_item.backend,
            submission_id=submission_id,
            requested_condition=planned.agent_condition.identity,
            started_at=started_at,
            finished_at=finished_at,
            process_status=AttemptProcessStatus.UNKNOWN,
            cancellation_status=CancellationStatus.NOT_REQUESTED,
            resource_usage=AttemptResourceUsage(wall_seconds=max(0.0, (finished_at - started_at).total_seconds())),
            failure=FailureClassification(
                failure_class=FailureClass.UNKNOWN,
                kind=FailureKind.UNKNOWN_EXTERNAL_STATE,
                message="Harbor did not provide a reconciled terminal result",
            ),
            reconciliation_status=ReconciliationState.PENDING,
        )
        self._persist_receipt(receipt)
        self._operational_store.transition_attempt(
            attempt.attempt_id,
            state="unknown",
            now=finished_at,
            failure=receipt.failure,
            reconciliation_state=receipt.reconciliation_status.value,
        )
        self._operational_store.transition_backend_submission(
            submission_id,
            state="unknown",
            now=finished_at,
            reconciliation_state=receipt.reconciliation_status.value,
        )
        return WorkerOutcome(terminal_state="unknown", receipts=(receipt,))

    def _existing_published_outcome(
        self,
        attempt: AttemptRecord,
        planned: PlannedTrial,
        submission: BackendSubmissionRecord,
        spec: ResolvedRunSpec,
    ) -> WorkerOutcome | None:
        """Recover a portable final result that committed before operational state."""

        record_path = self._record_path(planned)
        finalization_path = self._finalization_path(planned)
        if not record_path.exists() and not finalization_path.exists():
            return None
        if not record_path.is_file() or not finalization_path.is_file():
            raise HarborBackendError(f"trial publication is incomplete: {planned.trial_id}")
        try:
            record = read_trial_record(record_path)
            finalization = TrialFinalization.model_validate_json(finalization_path.read_text(encoding="utf-8"))
        except (OSError, RuntimeError, ValueError) as error:
            raise HarborBackendError(f"published trial evidence is invalid: {planned.trial_id}") from error
        task_revision = (
            planned.task_release.artifact.sha256
            if isinstance(planned.task_release, ArtifactTaskSnapshotRef)
            else planned.task_release.source_revision
            if isinstance(planned.task_release, RepositoryTaskSnapshotRef)
            else record.input.task_revision
        )
        validate_planned_trial_record(record, planned, spec, task_revision=task_revision)
        expected_ref = PortableRelativePath(record_path.relative_to(self._evidence_store.root).as_posix())
        if (
            finalization.trial_id != planned.trial_id
            or str(finalization.attempt_id) != attempt.attempt_id
            or finalization.trial_record_ref != expected_ref
        ):
            raise HarborBackendError(f"published trial finalization does not match the attempt: {planned.trial_id}")
        receipts = tuple(
            receipt
            for receipt in self._receipts_for_attempt(attempt)
            if receipt.process_status in {AttemptProcessStatus.SUCCEEDED, AttemptProcessStatus.FAILED}
        )
        if len(receipts) != 1:
            raise HarborBackendError(f"published trial requires one terminal attempt receipt: {planned.trial_id}")
        receipt = receipts[0]
        terminal_state: Literal["succeeded", "failed"] = (
            "succeeded" if receipt.process_status is AttemptProcessStatus.SUCCEEDED else "failed"
        )
        now = datetime.now(UTC)
        self._operational_store.transition_attempt(
            attempt.attempt_id,
            state=terminal_state,
            now=now,
            failure=receipt.failure,
            reconciliation_state="reconciled",
        )
        self._operational_store.transition_backend_submission(
            submission.submission_id,
            state="completed" if terminal_state == "succeeded" else "failed",
            now=now,
            reconciliation_state="reconciled",
        )
        return WorkerOutcome(terminal_state=terminal_state, receipts=(receipt,), finalization=finalization)

    def _canonical_record(
        self,
        record: TrialRecord,
        planned: PlannedTrial,
        spec: ResolvedRunSpec,
        *,
        harbor_trial_name: str,
        external_id: str,
    ) -> TrialRecord:
        task_revision = (
            planned.task_release.artifact.sha256
            if isinstance(planned.task_release, ArtifactTaskSnapshotRef)
            else planned.task_release.source_revision
            if isinstance(planned.task_release, RepositoryTaskSnapshotRef)
            else record.input.task_revision
        )
        if record.trial_id == str(planned.trial_id):
            validate_planned_trial_record(record, planned, spec, task_revision=task_revision)
            return self._with_backend_ids(record, harbor_trial_name=harbor_trial_name, external_id=external_id)
        transport = HarborTrialTransport(
            harbor_job_name=f"aec-planned-{planned.trial_id.hex}",
            planned_trial_id=planned.trial_id,
            harbor_trial_name=harbor_trial_name,
        )
        records, _ = reconcile_harbor_trial_records(
            records=(record,),
            run_spec=spec,
            run_plan=self._plan,
            transport=(transport,),
        )
        canonical = records[0]
        validate_planned_trial_record(canonical, planned, spec, task_revision=task_revision)
        return self._with_backend_ids(canonical, harbor_trial_name=harbor_trial_name, external_id=external_id)

    @staticmethod
    def _with_backend_ids(record: TrialRecord, *, harbor_trial_name: str, external_id: str) -> TrialRecord:
        if record.output is None:
            return record
        backend_ids = dict(record.output.agent_result or {})
        backend_ids["harbor_trial_name"] = harbor_trial_name
        backend_ids["harbor_external_id"] = external_id
        return record.model_copy(update={"output": record.output.model_copy(update={"agent_result": backend_ids})})

    def _planned_trial(self, work_item: WorkItemRecord) -> PlannedTrial:
        if work_item.run_id != str(self._plan.run_id) or work_item.plan_id != str(self._plan.plan_id):
            raise HarborBackendError("work item does not belong to the authoritative run plan")
        matches = [trial for trial in self._plan.trials if str(trial.trial_id) == work_item.trial_id]
        if len(matches) != 1:
            raise HarborBackendError(f"work item does not identify one planned trial: {work_item.trial_id}")
        planned = matches[0]
        if planned.execution_family != "artifact":
            raise HarborBackendError("Harbor currently supports artifact trials only")
        if planned.ordinal != work_item.ordinal or planned.compute.backend != work_item.backend:
            raise HarborBackendError("work item does not match the authoritative planned trial")
        return planned

    @staticmethod
    def _validate_attempt(
        work_item: WorkItemRecord, attempt: AttemptRecord, *, allow_reconciliation: bool = False
    ) -> None:
        valid_work_states = {"running", "unknown"} if allow_reconciliation else {"running"}
        valid_attempt_states = {"running", "unknown"} if allow_reconciliation else {"running"}
        if work_item.state not in valid_work_states or attempt.state not in valid_attempt_states:
            raise HarborBackendError("Harbor execution requires a running work item and attempt")
        if attempt.work_id != work_item.work_id or attempt.trial_id != work_item.trial_id:
            raise HarborBackendError("scheduler attempt does not match the work item")
        if attempt.run_id != work_item.run_id or attempt.lease_id is None:
            raise HarborBackendError("Harbor execution requires a matching lease-bound attempt")

    def _persist_transport(self, transport: HarborAttemptTransport) -> None:
        path = (
            self._evidence_store.run_directory(self._plan.run_identity)
            / "harbor-mappings"
            / f"{transport.submission_id}.json"
        )
        try:
            write_append_only_json_at(path=path, payload=transport.model_dump_json(indent=2) + "\n")
        except DuplicateAppendOnlyFileError as error:
            raise HarborBackendError(f"Harbor transport mapping already exists: {transport.submission_id}") from error

    def _persist_receipt(self, receipt: AttemptReceipt) -> None:
        path = self._evidence_store.run_directory(self._plan.run_identity) / "receipts" / f"{receipt.receipt_id}.json"
        try:
            write_append_only_json_at(path=path, payload=receipt.model_dump_json(indent=2) + "\n")
        except DuplicateAppendOnlyFileError as error:
            raise HarborBackendError(f"attempt receipt already exists: {receipt.receipt_id}") from error

    def _existing_unknown_outcome(
        self,
        work_item: WorkItemRecord,
        attempt: AttemptRecord,
        planned: PlannedTrial,
        submission_id: UUID,
    ) -> WorkerOutcome:
        for receipt in self._receipts_for_attempt(attempt):
            if str(receipt.attempt_id) == attempt.attempt_id and receipt.process_status is AttemptProcessStatus.UNKNOWN:
                return WorkerOutcome(terminal_state="unknown", receipts=(receipt,))
        return self._unknown_outcome(
            work_item, attempt, planned, submission_id, attempt.started_at or attempt.created_at
        )

    def _receipts_for_attempt(self, attempt: AttemptRecord) -> tuple[AttemptReceipt, ...]:
        receipt_dir = self._evidence_store.run_directory(self._plan.run_identity) / "receipts"
        receipts: list[AttemptReceipt] = []
        for path in sorted(receipt_dir.glob("*.json")):
            try:
                receipt = AttemptReceipt.model_validate(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError):
                continue
            if str(receipt.attempt_id) == attempt.attempt_id:
                receipts.append(receipt)
        return tuple(receipts)

    def _record_path(self, planned: PlannedTrial) -> Path:
        return (
            self._evidence_store.run_directory(self._plan.run_identity) / "trial-records" / f"{planned.trial_id}.json"
        )

    def _finalization_path(self, planned: PlannedTrial) -> Path:
        return (
            self._evidence_store.run_directory(self._plan.run_identity) / "finalizations" / f"{planned.trial_id}.json"
        )

    def _receipt(
        self,
        *,
        work_item: WorkItemRecord,
        attempt: AttemptRecord,
        planned: PlannedTrial,
        submission_id: UUID,
        record: TrialRecord,
        started_at: datetime,
        finished_at: datetime,
        succeeded: bool,
    ) -> AttemptReceipt:
        output_references = () if record.output is None else tuple(item.artifact for item in record.output.artifacts)
        return AttemptReceipt(
            receipt_id=new_entity_id(EntityKind.RECEIPT),
            receipt_key=EntityKey(f"{work_item.work_key}/attempt-{attempt.attempt_number}"),
            attempt_id=validate_uuidv7(attempt.attempt_id),
            backend=work_item.backend,
            submission_id=submission_id,
            requested_condition=planned.agent_condition.identity,
            started_at=started_at,
            finished_at=finished_at,
            process_status=AttemptProcessStatus.SUCCEEDED if succeeded else AttemptProcessStatus.FAILED,
            cancellation_status=CancellationStatus.NOT_REQUESTED,
            resource_usage=AttemptResourceUsage(wall_seconds=record.timing.total_seconds),
            output_references=output_references,
            authority_evidence=record.authority_evidence,
            failure=(
                None
                if succeeded
                else FailureClassification(
                    failure_class=FailureClass.BENCHMARK,
                    kind=FailureKind.TASK_FAILURE,
                    message="Harbor reported failed execution",
                )
            ),
            reconciliation_status=ReconciliationState.RECONCILED,
        )

    def _mark_failed(self, attempt: AttemptRecord, submission_id: UUID) -> None:
        now = datetime.now(UTC)
        try:
            self._operational_store.transition_attempt(attempt.attempt_id, state="failed", now=now)
            self._operational_store.transition_backend_submission(submission_id, state="failed", now=now)
        except OperationalStoreError:
            pass


__all__ = (
    "HarborAttemptTransport",
    "HarborBackend",
    "HarborBackendClient",
    "HarborBackendError",
    "HarborRemoteState",
    "HarborSubmission",
)
