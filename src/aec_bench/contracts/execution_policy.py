# ABOUTME: Defines the resolved provider-neutral execution limits for one run.
# ABOUTME: Keeps scheduler policy at the foundational contract boundary for persistence and inspection.

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.identity import validate_uuidv7
from aec_bench.contracts.validators import FrozenStrictModel


class FailureClass(StrEnum):
    """Broad class used to decide whether an attempt may be retried."""

    INFRASTRUCTURE = "infrastructure"
    BENCHMARK = "benchmark"
    INVALIDATING = "invalidating"
    UNKNOWN = "unknown"


class FailureKind(StrEnum):
    """Specific provider-neutral failure facts available to retry policy."""

    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TRANSPORT_UNAVAILABLE = "transport_unavailable"
    SUBMISSION_REJECTED = "submission_rejected"
    WORKER_LOST_BEFORE_SUBMISSION = "worker_lost_before_submission"
    RESULT_IMPORT_FAILED = "result_import_failed"
    STORAGE_BUSY = "storage_busy"
    INVALID_OUTPUT = "invalid_output"
    VERIFIER_FAILURE = "verifier_failure"
    TASK_FAILURE = "task_failure"
    BUDGET_EXHAUSTED = "budget_exhausted"
    IDENTITY_MISMATCH = "identity_mismatch"
    HIDDEN_DATA_EXPOSURE = "hidden_data_exposure"
    LIMIT_NOT_ENFORCED = "limit_not_enforced"
    AUTHORITY_EVIDENCE_MISSING = "authority_evidence_missing"
    CONFLICTING_FINAL_RECORD = "conflicting_final_record"
    UNKNOWN_EXTERNAL_STATE = "unknown_external_state"


_FAILURE_CLASS_BY_KIND: dict[FailureKind, FailureClass] = {
    FailureKind.PROVIDER_UNAVAILABLE: FailureClass.INFRASTRUCTURE,
    FailureKind.TRANSPORT_UNAVAILABLE: FailureClass.INFRASTRUCTURE,
    FailureKind.SUBMISSION_REJECTED: FailureClass.INFRASTRUCTURE,
    FailureKind.WORKER_LOST_BEFORE_SUBMISSION: FailureClass.INFRASTRUCTURE,
    FailureKind.RESULT_IMPORT_FAILED: FailureClass.INFRASTRUCTURE,
    FailureKind.STORAGE_BUSY: FailureClass.INFRASTRUCTURE,
    FailureKind.INVALID_OUTPUT: FailureClass.BENCHMARK,
    FailureKind.VERIFIER_FAILURE: FailureClass.BENCHMARK,
    FailureKind.TASK_FAILURE: FailureClass.BENCHMARK,
    FailureKind.BUDGET_EXHAUSTED: FailureClass.BENCHMARK,
    FailureKind.IDENTITY_MISMATCH: FailureClass.INVALIDATING,
    FailureKind.HIDDEN_DATA_EXPOSURE: FailureClass.INVALIDATING,
    FailureKind.LIMIT_NOT_ENFORCED: FailureClass.INVALIDATING,
    FailureKind.AUTHORITY_EVIDENCE_MISSING: FailureClass.INVALIDATING,
    FailureKind.CONFLICTING_FINAL_RECORD: FailureClass.INVALIDATING,
    FailureKind.UNKNOWN_EXTERNAL_STATE: FailureClass.UNKNOWN,
}


def failure_class_for_kind(kind: FailureKind) -> FailureClass:
    """Return the fixed failure class for one provider-neutral failure kind."""

    return _FAILURE_CLASS_BY_KIND[kind]


class RetryPolicy(FrozenStrictModel):
    """Explicit retry inputs resolved as part of one run execution policy."""

    maximum_attempts: Annotated[int, Field(strict=True, gt=0)] = 1
    retryable_failure_kinds: tuple[FailureKind, ...] = ()
    backoff_seconds: Annotated[float, Field(strict=True, ge=0)] = 0.0
    maximum_elapsed_seconds: Annotated[float, Field(strict=True, gt=0)] | None = None
    unknown_state_policy: Literal["reconcile_before_retry", "never_retry"] = "reconcile_before_retry"

    @field_validator("retryable_failure_kinds")
    @classmethod
    def validate_unique_failure_kinds(cls, value: tuple[FailureKind, ...]) -> tuple[FailureKind, ...]:
        if len(value) != len(set(value)):
            raise ValueError("retryable failure kinds must be unique")
        if any(failure_class_for_kind(kind) is not FailureClass.INFRASTRUCTURE for kind in value):
            raise ValueError("automatic retry kinds must be infrastructure failures")
        return value

    @model_validator(mode="after")
    def validate_attempt_limit(self) -> Self:
        if self.maximum_attempts == 1 and self.retryable_failure_kinds:
            raise ValueError("single-attempt policy must not declare retryable failure kinds")
        if self.maximum_attempts > 1 and not self.retryable_failure_kinds:
            raise ValueError("multi-attempt policy requires retryable failure kinds")
        return self


class ExecutionPolicy(FrozenStrictModel):
    """Resolved local execution limits and fairness settings for one run."""

    schema_version: Literal[1] = 1
    max_concurrency: Annotated[int, Field(strict=True, gt=0)]
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    lease_ttl_seconds: Annotated[int, Field(strict=True, gt=0)] = 300
    lease_heartbeat_seconds: Annotated[int, Field(strict=True, gt=0)] = 30
    priority_aging_seconds: Annotated[int, Field(strict=True, gt=0)] = 300
    run_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)
    backend_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)
    provider_route_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)
    model_route_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)
    resource_class_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)
    execution_family_limits: dict[str, Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=dict)

    @field_validator(
        "run_limits",
        "backend_limits",
        "provider_route_limits",
        "model_route_limits",
        "resource_class_limits",
        "execution_family_limits",
    )
    @classmethod
    def validate_limit_keys(cls, value: dict[str, int], info: object) -> dict[str, int]:
        for key in value:
            if not isinstance(key, str) or not key.strip():
                raise ValueError("concurrency limit keys must not be blank")
        if getattr(info, "field_name", None) == "run_limits":
            for key in value:
                validate_uuidv7(key)
        return value

    @model_validator(mode="after")
    def validate_limits(self) -> Self:
        if self.lease_heartbeat_seconds >= self.lease_ttl_seconds:
            raise ValueError("lease heartbeat interval must be shorter than lease ttl")
        if any(limit > self.max_concurrency for limits in self._limit_groups() for limit in limits.values()):
            raise ValueError("a concurrency limit must not exceed max_concurrency")
        return self

    def _limit_groups(self) -> tuple[Mapping[str, int], ...]:
        return (
            self.run_limits,
            self.backend_limits,
            self.provider_route_limits,
            self.model_route_limits,
            self.resource_class_limits,
            self.execution_family_limits,
        )


__all__ = ("ExecutionPolicy", "FailureClass", "FailureKind", "RetryPolicy", "failure_class_for_kind")
