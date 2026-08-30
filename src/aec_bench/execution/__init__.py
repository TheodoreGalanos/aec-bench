# ABOUTME: Owns provider-neutral execution orchestration boundaries.
# ABOUTME: Keeps mutable operational state separate from task semantics and evidence storage.

"""Execution composition boundaries."""

from aec_bench.contracts.execution_policy import ExecutionPolicy
from aec_bench.execution.models import (
    Attempt,
    AttemptProcessStatus,
    AttemptReceipt,
    AttemptResourceUsage,
    AttemptState,
    BackendSubmission,
    BackendSubmissionState,
    CancellationStatus,
    FailureClass,
    FailureClassification,
    FailureKind,
    FinalizationState,
    Lease,
    LeaseState,
    ReconciliationState,
    RetryPolicy,
    TrialFinalization,
    TrialWorkItem,
    WorkerOutcome,
    WorkItemState,
)
from aec_bench.execution.progress import (
    AttemptProgressCounts,
    BackendSubmissionProgressCounts,
    RunProgress,
    TrialProgressCounts,
    WorkItemProgressCounts,
    project_run_progress,
)
from aec_bench.execution.scheduler import LocalScheduler, SchedulerRunReport

__all__ = (
    "Attempt",
    "AttemptProcessStatus",
    "AttemptReceipt",
    "AttemptResourceUsage",
    "AttemptState",
    "BackendSubmission",
    "BackendSubmissionState",
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
    "AttemptProgressCounts",
    "BackendSubmissionProgressCounts",
    "RunProgress",
    "TrialProgressCounts",
    "WorkItemProgressCounts",
    "project_run_progress",
    "LocalScheduler",
    "ExecutionPolicy",
    "SchedulerRunReport",
)
