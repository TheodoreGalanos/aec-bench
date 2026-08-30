# ABOUTME: Defines provider-neutral PRD3 work, attempt, lease, receipt, and finalization contracts.
# ABOUTME: Keeps execution control strict while leaving task meaning and evidence authority with existing owners.

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, NonNegativeFloat, NonNegativeInt, PositiveInt, field_validator, model_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.authority_evidence import AuthorityEvidenceRef
from aec_bench.contracts.execution_policy import (
    FailureClass,
    FailureKind,
    RetryPolicy,
    failure_class_for_kind,
)
from aec_bench.contracts.identity import EntityIdentity, EntityKey, PortableRelativePath, validate_uuidv7
from aec_bench.contracts.runtime_observation import RuntimeObservation
from aec_bench.contracts.trial_extensions import VerifierExecutionReceipt
from aec_bench.contracts.trial_record import TrialTaskKind
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class WorkItemState(StrEnum):
    PLANNED = "planned"
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class AttemptState(StrEnum):
    CREATED = "created"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class LeaseState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    RELEASED = "released"


class BackendSubmissionState(StrEnum):
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ReconciliationState(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    RECONCILED = "reconciled"
    UNKNOWN = "unknown"


class FinalizationState(StrEnum):
    CURRENT = "current"
    SUPERSEDED = "superseded"


class AttemptProcessStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class CancellationStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class BackendCancellationResult(FrozenStrictModel):
    """Provider-neutral result of one backend cancellation request."""

    status: Literal["confirmed", "rejected", "unsupported", "unknown"]
    message: NonEmptyStr


class FailureClassification(FrozenStrictModel):
    """Provider-neutral classification of one failed or uncertain attempt."""

    failure_class: FailureClass
    kind: FailureKind
    message: NonEmptyStr

    @model_validator(mode="after")
    def validate_class(self) -> Self:
        expected = failure_class_for_kind(self.kind)
        if self.failure_class is not expected:
            raise ValueError(f"failure kind {self.kind} requires class {expected}")
        return self


class AttemptResourceUsage(FrozenStrictModel):
    """Measured resource use reported by one backend attempt."""

    wall_seconds: NonNegativeFloat
    cpu_seconds: NonNegativeFloat | None = None
    peak_memory_bytes: NonNegativeInt | None = None
    input_tokens: NonNegativeInt | None = None
    output_tokens: NonNegativeInt | None = None
    estimated_cost_usd: NonNegativeFloat | None = None


class TrialWorkItem(FrozenStrictModel):
    """One schedulable work item for one planned trial."""

    schema_version: Literal[1] = 1
    work_id: UUID
    work_key: EntityKey
    run_id: UUID
    plan_id: UUID
    trial_id: UUID
    ordinal: PositiveInt
    execution_family: TrialTaskKind
    backend: NonEmptyStr
    provider_route: NonEmptyStr
    model_route: NonEmptyStr
    resource_class: NonEmptyStr
    priority: Annotated[int, Field(strict=True)] = 0
    retry_policy: RetryPolicy
    state: WorkItemState
    created_at: datetime
    available_at: datetime
    current_attempt_number: Annotated[int, Field(strict=True, ge=0)] = 0

    @field_validator("work_id", "run_id", "plan_id", "trial_id", mode="before")
    @classmethod
    def validate_ids(cls, value: UUID | str) -> UUID:
        return validate_uuidv7(value)

    @field_validator("created_at", "available_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime) -> datetime:
        return _aware(value, "work item timestamp")

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        if self.available_at < self.created_at:
            raise ValueError("work item available_at must not precede created_at")
        return self


class Attempt(FrozenStrictModel):
    """One execution try under a stable trial and work-item identity."""

    schema_version: Literal[1] = 1
    attempt_id: UUID
    attempt_key: EntityKey
    version: PositiveInt = 1
    run_id: UUID
    trial_id: UUID
    work_id: UUID
    attempt_number: PositiveInt
    candidate_index: PositiveInt
    retry_number: NonNegativeInt
    backend_submission_id: UUID | None = None
    lease_id: UUID | None = None
    worker_id: EntityKey | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    state: AttemptState
    failure: FailureClassification | None = None
    runtime_observation: RuntimeObservation | None = None
    verifier_receipt: VerifierExecutionReceipt | None = None
    result_ref: PortableRelativePath | None = None

    @field_validator(
        "attempt_id",
        "run_id",
        "trial_id",
        "work_id",
        "backend_submission_id",
        "lease_id",
        mode="before",
    )
    @classmethod
    def validate_ids(cls, value: UUID | str | None) -> UUID | None:
        return None if value is None else validate_uuidv7(value)

    @field_validator("started_at", "finished_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware(value, "attempt timestamp")

    @model_validator(mode="after")
    def validate_attempt(self) -> Self:
        if self.started_at is not None and self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("attempt finished_at must not precede started_at")
        if self.state is AttemptState.CREATED and (self.started_at is not None or self.finished_at is not None):
            raise ValueError("created attempt must not have execution timestamps")
        if self.state in {AttemptState.RUNNING, AttemptState.SUCCEEDED, AttemptState.FAILED, AttemptState.CANCELLED}:
            if self.started_at is None:
                raise ValueError(f"{self.state} attempt requires started_at")
        if self.state in {AttemptState.SUCCEEDED, AttemptState.FAILED, AttemptState.CANCELLED, AttemptState.UNKNOWN}:
            if self.finished_at is None:
                raise ValueError(f"{self.state} attempt requires finished_at")
        if self.state is AttemptState.RUNNING and self.finished_at is not None:
            raise ValueError("running attempt must not have finished_at")
        if self.state in {AttemptState.SUBMITTED, AttemptState.RUNNING, AttemptState.SUCCEEDED}:
            if self.backend_submission_id is None:
                raise ValueError(f"{self.state} attempt requires backend_submission_id")
        if self.state in {AttemptState.FAILED, AttemptState.UNKNOWN} and self.failure is None:
            raise ValueError("failed or unknown attempt requires a failure classification")
        if self.state is AttemptState.SUCCEEDED and self.failure is not None:
            raise ValueError("succeeded attempt must not carry a failure classification")
        if self.state is AttemptState.SUCCEEDED and self.result_ref is None:
            raise ValueError("succeeded attempt requires result_ref")
        if self.state is AttemptState.CANCELLED and self.failure is not None:
            raise ValueError("cancelled attempt must not carry a failure classification")
        if (
            self.failure is not None
            and self.failure.kind is FailureKind.UNKNOWN_EXTERNAL_STATE
            and self.backend_submission_id is None
        ):
            raise ValueError("unknown external state requires backend_submission_id")
        if self.runtime_observation is not None:
            if self.runtime_observation.attempt_id != self.attempt_id:
                raise ValueError("runtime observation attempt_id must match attempt")
            if self.runtime_observation.trial_id != self.trial_id:
                raise ValueError("runtime observation trial_id must match attempt")
        return self


class Lease(FrozenStrictModel):
    """One worker lease for a work item."""

    schema_version: Literal[1] = 1
    lease_id: UUID
    work_id: UUID
    worker_id: NonEmptyStr
    acquired_at: datetime
    expires_at: datetime
    heartbeat_at: datetime
    state: LeaseState
    released_at: datetime | None = None

    @field_validator("lease_id", "work_id", mode="before")
    @classmethod
    def validate_ids(cls, value: UUID | str) -> UUID:
        return validate_uuidv7(value)

    @field_validator("acquired_at", "expires_at", "heartbeat_at", "released_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware(value, "lease timestamp")

    @model_validator(mode="after")
    def validate_lease(self) -> Self:
        if self.expires_at <= self.acquired_at:
            raise ValueError("lease expires_at must be after acquired_at")
        if self.heartbeat_at < self.acquired_at:
            raise ValueError("lease heartbeat_at must not precede acquired_at")
        if self.heartbeat_at > self.expires_at:
            raise ValueError("lease heartbeat_at must not follow expires_at")
        if self.released_at is not None and self.released_at < self.acquired_at:
            raise ValueError("lease released_at must not precede acquired_at")
        if self.state is LeaseState.ACTIVE and self.released_at is not None:
            raise ValueError("active lease must not have released_at")
        if self.state is not LeaseState.ACTIVE and self.released_at is None:
            raise ValueError("inactive lease requires released_at")
        return self


class BackendSubmission(FrozenStrictModel):
    """Backend submission identity and mutable provider status."""

    schema_version: Literal[1] = 1
    submission_id: UUID
    attempt_id: UUID
    backend: NonEmptyStr
    external_id: NonEmptyStr | None = None
    state: BackendSubmissionState
    submitted_at: datetime
    updated_at: datetime

    @field_validator("submission_id", "attempt_id", mode="before")
    @classmethod
    def validate_ids(cls, value: UUID | str) -> UUID:
        return validate_uuidv7(value)

    @field_validator("submitted_at", "updated_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime) -> datetime:
        return _aware(value, "submission timestamp")

    @model_validator(mode="after")
    def validate_update_time(self) -> Self:
        if self.updated_at < self.submitted_at:
            raise ValueError("submission updated_at must not precede submitted_at")
        if (
            self.state
            in {
                BackendSubmissionState.ACCEPTED,
                BackendSubmissionState.RUNNING,
                BackendSubmissionState.COMPLETED,
            }
            and self.external_id is None
        ):
            raise ValueError(f"{self.state} submission requires external_id")
        return self


class AttemptReceipt(FrozenStrictModel):
    """Versioned provider-neutral receipt for one collected attempt."""

    schema_version: Literal[1] = 1
    receipt_id: UUID
    receipt_key: EntityKey
    version: PositiveInt = 1
    attempt_id: UUID
    backend: NonEmptyStr
    submission_id: UUID
    requested_condition: EntityIdentity
    runtime_observation: RuntimeObservation | None = None
    started_at: datetime
    finished_at: datetime
    process_status: AttemptProcessStatus
    cancellation_status: CancellationStatus
    resource_usage: AttemptResourceUsage
    output_references: tuple[ArtifactRef, ...] = ()
    verifier_receipt: VerifierExecutionReceipt | None = None
    authority_evidence: tuple[AuthorityEvidenceRef, ...] = ()
    failure: FailureClassification | None = None
    reconciliation_status: ReconciliationState

    @field_validator("receipt_id", "attempt_id", "submission_id", mode="before")
    @classmethod
    def validate_ids(cls, value: UUID | str) -> UUID:
        return validate_uuidv7(value)

    @field_validator("started_at", "finished_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime) -> datetime:
        return _aware(value, "receipt timestamp")

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("receipt finished_at must not precede started_at")
        if self.runtime_observation is not None and self.runtime_observation.attempt_id != self.attempt_id:
            raise ValueError("runtime observation attempt_id must match receipt")
        if self.process_status in {AttemptProcessStatus.FAILED, AttemptProcessStatus.UNKNOWN} and self.failure is None:
            raise ValueError("failed or unknown receipt requires a failure classification")
        if self.process_status is AttemptProcessStatus.SUCCEEDED and self.failure is not None:
            raise ValueError("succeeded receipt must not carry a failure classification")
        if (
            self.process_status is AttemptProcessStatus.SUCCEEDED
            and not self.output_references
            and self.verifier_receipt is None
            and not self.authority_evidence
        ):
            raise ValueError("succeeded receipt requires retained output or authority evidence")
        if self.process_status is AttemptProcessStatus.CANCELLED and self.cancellation_status not in {
            CancellationStatus.CONFIRMED,
            CancellationStatus.UNKNOWN,
        }:
            raise ValueError("cancelled receipt requires confirmed or unknown cancellation status")
        output_ids = tuple(reference.artifact_id for reference in self.output_references)
        if len(output_ids) != len(set(output_ids)):
            raise ValueError("attempt receipt output references must be unique")
        authority_ids = tuple(
            (reference.authority_kind, reference.protocol, reference.artifact.artifact_id)
            for reference in self.authority_evidence
        )
        if len(authority_ids) != len(set(authority_ids)):
            raise ValueError("attempt receipt authority evidence references must be unique")
        return self


class TrialFinalization(FrozenStrictModel):
    """Versioned pointer to one published final trial record."""

    schema_version: Literal[1] = 1
    finalization_id: UUID
    trial_id: UUID
    attempt_id: UUID
    record_version: PositiveInt
    trial_record_ref: PortableRelativePath
    published_at: datetime
    supersedes_finalization_id: UUID | None = None
    state: FinalizationState

    @field_validator("finalization_id", "trial_id", "attempt_id", "supersedes_finalization_id", mode="before")
    @classmethod
    def validate_ids(cls, value: UUID | str | None) -> UUID | None:
        return None if value is None else validate_uuidv7(value)

    @field_validator("published_at")
    @classmethod
    def validate_aware_timestamp(cls, value: datetime) -> datetime:
        return _aware(value, "finalization timestamp")

    @model_validator(mode="after")
    def validate_supersession(self) -> Self:
        if self.supersedes_finalization_id == self.finalization_id:
            raise ValueError("finalization must not supersede itself")
        return self


class WorkerOutcome(FrozenStrictModel):
    """Strict terminal result returned by an adapter to the scheduler."""

    schema_version: Literal[1] = 1
    terminal_state: Literal["succeeded", "failed", "unknown"]
    receipts: tuple[AttemptReceipt, ...]
    finalization: TrialFinalization | None = None

    @model_validator(mode="after")
    def validate_receipts(self) -> Self:
        if not self.receipts:
            raise ValueError("worker outcome requires at least one attempt receipt")
        if self.terminal_state == "unknown" and self.finalization is not None:
            raise ValueError("unknown worker outcome must not have a finalization")
        if self.terminal_state == "succeeded" and self.finalization is None:
            raise ValueError("succeeded worker outcome requires a finalization")
        if self.terminal_state == "failed" and self.finalization is None:
            if not any(
                receipt.failure is not None and receipt.failure.failure_class is FailureClass.INFRASTRUCTURE
                for receipt in self.receipts
            ):
                raise ValueError("failed worker outcome without finalization requires an infrastructure failure")
            return self
        if self.finalization is None:
            return self
        if self.finalization.attempt_id not in {receipt.attempt_id for receipt in self.receipts}:
            raise ValueError("worker outcome finalization attempt must have a receipt")
        selected = next(receipt for receipt in self.receipts if receipt.attempt_id == self.finalization.attempt_id)
        if self.terminal_state == "succeeded" and selected.process_status is not AttemptProcessStatus.SUCCEEDED:
            raise ValueError("succeeded worker outcome requires a succeeded finalization receipt")
        return self


def _aware(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return value


__all__ = (
    "Attempt",
    "AttemptProcessStatus",
    "AttemptReceipt",
    "AttemptResourceUsage",
    "AttemptState",
    "BackendSubmission",
    "BackendSubmissionState",
    "BackendCancellationResult",
    "CancellationStatus",
    "FailureClass",
    "FailureClassification",
    "FailureKind",
    "FinalizationState",
    "Lease",
    "LeaseState",
    "ReconciliationState",
    "RetryPolicy",
    "TrialFinalization",
    "TrialWorkItem",
    "WorkerOutcome",
    "WorkItemState",
)
