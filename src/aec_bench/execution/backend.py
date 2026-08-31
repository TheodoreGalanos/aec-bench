# ABOUTME: Defines the narrow backend control boundary used by cancellation and reconciliation.
# ABOUTME: Keeps transport actions fakeable without moving retry or benchmark policy into a backend.

from __future__ import annotations

from typing import Protocol

from aec_bench.execution.models import BackendCancellationResult, WorkerOutcome
from aec_bench.execution.operational import AttemptRecord, BackendSubmissionRecord, WorkItemRecord


class ExecutionBackendControl(Protocol):
    """Backend operations needed after a scheduler attempt has been submitted."""

    def cancel(
        self, work_item: WorkItemRecord, attempt: AttemptRecord, submission: BackendSubmissionRecord
    ) -> BackendCancellationResult: ...

    def reconcile(
        self, work_item: WorkItemRecord, attempt: AttemptRecord, submission: BackendSubmissionRecord
    ) -> WorkerOutcome: ...


__all__ = ("ExecutionBackendControl",)
