# ABOUTME: Composes the authoritative portable run plan with mutable progress state.
# ABOUTME: Keeps filesystem loading out of the provider-neutral progress projection.

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import NonNegativeInt

from aec_bench.contracts.validators import FrozenStrictModel
from aec_bench.execution.operational.store import OperationalStore
from aec_bench.execution.progress import (
    AttemptProgressCounts,
    BackendSubmissionProgressCounts,
    RunProgress,
    TrialProgressCounts,
    WorkItemProgressCounts,
    project_run_progress,
)
from aec_bench.ledger.evidence_run_store import EvidenceRunStore, EvidenceRunStoreError


class RunProgressSurface(FrozenStrictModel):
    """Flat presentation contract derived from one validated RunProgress."""

    schema_version: Literal[1] = 1
    run_id: UUID
    plan_id: UUID
    status: Literal["created", "ready", "running", "completed", "failed", "cancelled"]
    planned: NonNegativeInt
    succeeded: NonNegativeInt
    failed: NonNegativeInt
    running: NonNegativeInt
    queued: NonNegativeInt
    unknown: NonNegativeInt
    cancelled: NonNegativeInt
    retries: NonNegativeInt
    work_items: WorkItemProgressCounts
    trials: TrialProgressCounts
    attempts: AttemptProgressCounts
    backend_submissions: BackendSubmissionProgressCounts
    active_leases: NonNegativeInt
    expired_leases: NonNegativeInt
    started_at: datetime | None
    last_activity_at: datetime | None
    estimated_remaining_work_count: NonNegativeInt
    completion_blocked_by_non_terminal: bool
    completion_blocked_by_unknown: bool
    completion_blocked: bool


def present_run_progress(progress: RunProgress) -> RunProgressSurface:
    """Map the shared projection to the flat surface without recalculating it."""

    return RunProgressSurface(
        run_id=progress.run_id,
        plan_id=progress.plan_id,
        status=progress.status,
        planned=progress.planned,
        succeeded=progress.trials.succeeded,
        failed=progress.trials.failed,
        running=progress.trials.running,
        queued=progress.trials.queued,
        unknown=progress.trials.unknown,
        cancelled=progress.trials.cancelled,
        retries=progress.retries,
        work_items=progress.work_items,
        trials=progress.trials,
        attempts=progress.attempts,
        backend_submissions=progress.backend_submissions,
        active_leases=progress.active_leases,
        expired_leases=progress.expired_leases,
        started_at=progress.started_at,
        last_activity_at=progress.last_activity_at,
        estimated_remaining_work_count=progress.estimated_remaining_work_count,
        completion_blocked_by_non_terminal=progress.completion_blocked_by_non_terminal,
        completion_blocked_by_unknown=progress.completion_blocked_by_unknown,
        completion_blocked=progress.completion_blocked,
    )


def load_run_progress(
    run_id: str,
    *,
    operational_store_path: Path,
    plan_root: Path,
) -> RunProgress:
    """Load and project one exact run from two explicitly supplied roots."""

    stored = EvidenceRunStore.open_read_only(plan_root).find_run(run_id)
    if stored.plan is None:
        raise EvidenceRunStoreError(f"run has no persisted plan: {run_id}")
    return project_run_progress(stored.plan, OperationalStore.open_read_only(operational_store_path))


def load_run_progress_surface(
    run_id: str,
    *,
    operational_store_path: Path,
    plan_root: Path,
) -> RunProgressSurface:
    """Load and present one exact run using explicit roots."""

    return present_run_progress(
        load_run_progress(
            run_id,
            operational_store_path=operational_store_path,
            plan_root=plan_root,
        )
    )
