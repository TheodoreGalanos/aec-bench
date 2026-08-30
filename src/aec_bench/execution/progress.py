# ABOUTME: Defines the read-only run progress projection for PRD3 execution.
# ABOUTME: Derives operational counts from an authoritative RunPlan without hydrating evidence records.

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.identity import validate_uuidv7
from aec_bench.contracts.run_plan import RunPlan
from aec_bench.contracts.validators import FrozenStrictModel
from aec_bench.execution.operational import (
    AttemptRecord,
    BackendSubmissionRecord,
    OperationalStore,
    OperationalStoreError,
    PlannedTrialRecord,
    WorkItemRecord,
)


class WorkItemProgressCounts(FrozenStrictModel):
    """Counts for expected work items, including absent operational rows."""

    planned: NonNegativeInt = 0
    queued: NonNegativeInt = 0
    leased: NonNegativeInt = 0
    running: NonNegativeInt = 0
    cancel_requested: NonNegativeInt = 0
    succeeded: NonNegativeInt = 0
    failed: NonNegativeInt = 0
    cancelled: NonNegativeInt = 0
    invalid: NonNegativeInt = 0
    unknown: NonNegativeInt = 0
    missing: NonNegativeInt = 0


class TrialProgressCounts(FrozenStrictModel):
    """Counts for the authoritative planned trials and their operational rows."""

    planned: NonNegativeInt = 0
    queued: NonNegativeInt = 0
    running: NonNegativeInt = 0
    succeeded: NonNegativeInt = 0
    failed: NonNegativeInt = 0
    cancelled: NonNegativeInt = 0
    invalid: NonNegativeInt = 0
    unknown: NonNegativeInt = 0
    missing: NonNegativeInt = 0


class AttemptProgressCounts(FrozenStrictModel):
    """Counts of attempts grouped by their operational state."""

    created: NonNegativeInt = 0
    submitted: NonNegativeInt = 0
    running: NonNegativeInt = 0
    succeeded: NonNegativeInt = 0
    failed: NonNegativeInt = 0
    cancelled: NonNegativeInt = 0
    unknown: NonNegativeInt = 0


class BackendSubmissionProgressCounts(FrozenStrictModel):
    """Counts of backend submissions grouped by their observed state."""

    submitted: NonNegativeInt = 0
    accepted: NonNegativeInt = 0
    running: NonNegativeInt = 0
    completed: NonNegativeInt = 0
    failed: NonNegativeInt = 0
    unknown: NonNegativeInt = 0


class RunProgress(FrozenStrictModel):
    """A read-only operational view over one exact run plan."""

    schema_version: Literal[1] = 1
    run_id: UUID
    plan_id: UUID
    planned: NonNegativeInt
    work_items: WorkItemProgressCounts
    trials: TrialProgressCounts
    attempts: AttemptProgressCounts
    backend_submissions: BackendSubmissionProgressCounts
    active_leases: NonNegativeInt = 0
    expired_leases: NonNegativeInt = 0
    retries: NonNegativeInt = 0
    started_at: datetime | None = None
    last_activity_at: datetime | None = None
    estimated_remaining_work_count: NonNegativeInt
    completion_blocked_by_non_terminal: bool
    completion_blocked_by_unknown: bool
    completion_blocked: bool

    @field_validator("run_id", "plan_id")
    @classmethod
    def validate_ids(cls, value: UUID) -> UUID:
        return validate_uuidv7(value)

    @field_validator("started_at", "last_activity_at")
    @classmethod
    def validate_times(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("run progress timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_projection(self) -> Self:
        trial_total = sum(self.trials.model_dump().values())
        work_total = sum(self.work_items.model_dump().values())
        if trial_total != self.planned:
            raise ValueError("run progress trial counts must partition planned trials")
        if work_total != self.planned:
            raise ValueError("run progress work-item counts must partition planned trials")
        non_terminal = bool(
            self.trials.planned
            + self.trials.queued
            + self.trials.running
            + self.trials.unknown
            + self.trials.missing
            + self.work_items.planned
            + self.work_items.queued
            + self.work_items.leased
            + self.work_items.running
            + self.work_items.cancel_requested
            + self.work_items.unknown
            + self.work_items.missing
        )
        unknown = bool(self.trials.unknown or self.work_items.unknown)
        if self.completion_blocked_by_non_terminal != non_terminal:
            raise ValueError("run progress non-terminal blocker does not match counts")
        if self.completion_blocked_by_unknown != unknown:
            raise ValueError("run progress unknown blocker does not match counts")
        if self.completion_blocked != (non_terminal or unknown):
            raise ValueError("run progress completion blocker does not match counts")
        expected_remaining = (
            self.trials.planned + self.trials.queued + self.trials.running + self.trials.unknown + self.trials.missing
        )
        if self.estimated_remaining_work_count != expected_remaining:
            raise ValueError("run progress remaining count does not match non-terminal planned trials")
        if (
            self.started_at is not None
            and self.last_activity_at is not None
            and self.last_activity_at < self.started_at
        ):
            raise ValueError("run progress last_activity_at must not precede started_at")
        return self


def project_run_progress(run_plan: RunPlan, store: OperationalStore) -> RunProgress:
    """Project one authoritative plan and its mutable operational rows."""

    planned_ids = tuple(trial.trial_identity.id for trial in run_plan.trials)
    planned_id_set = set(planned_ids)
    run_record = store.get_run(run_plan.run_id)
    plan_record = store.get_plan(run_plan.plan_id)
    if plan_record.run_id != str(run_plan.run_id):
        raise OperationalStoreError(
            f"operational plan {run_plan.plan_id} belongs to run {plan_record.run_id}, "
            f"not authoritative run {run_plan.run_id}"
        )
    trial_rows = _validated_trial_rows(run_plan, store.list_planned_trials(run_plan.plan_id))
    work_rows = store.list_work_items(run_plan.run_id)
    expected_work_rows = {UUID(row.trial_id): row for row in work_rows if UUID(row.trial_id) in planned_id_set}
    expected_work_ids = {row.work_id for row in expected_work_rows.values()}
    expected_work_trial_ids = {row.work_id: str(trial_id) for trial_id, row in expected_work_rows.items()}
    attempts = tuple(
        attempt
        for attempt in store.list_attempts_for_run(run_plan.run_id)
        if attempt.work_id in expected_work_ids and attempt.trial_id == expected_work_trial_ids.get(attempt.work_id)
    )
    expected_attempt_ids = {attempt.attempt_id for attempt in attempts}
    leases = tuple(lease for lease in store.list_leases_for_run(run_plan.run_id) if lease.work_id in expected_work_ids)
    submissions = tuple(
        submission
        for submission in store.list_backend_submissions_for_run(run_plan.run_id)
        if submission.attempt_id in expected_attempt_ids
    )

    trial_counts = _trial_counts(planned_ids, trial_rows)
    work_counts = _work_counts(planned_ids, expected_work_rows)
    started_at = run_record.started_at
    activity_times = (
        [run_record.updated_at, plan_record.updated_at]
        + [row.updated_at for row in expected_work_rows.values()]
        + [row.updated_at for row in trial_rows.values()]
        + [attempt.updated_at for attempt in attempts]
        + [submission.updated_at for submission in submissions]
        + [lease.heartbeat_at for lease in leases]
    )
    last_activity_at = max(activity_times) if activity_times else None
    non_terminal = bool(
        trial_counts.planned
        + trial_counts.queued
        + trial_counts.running
        + trial_counts.unknown
        + trial_counts.missing
        + work_counts.planned
        + work_counts.queued
        + work_counts.leased
        + work_counts.running
        + work_counts.cancel_requested
        + work_counts.unknown
        + work_counts.missing
    )
    unknown = bool(trial_counts.unknown or work_counts.unknown)
    return RunProgress(
        run_id=run_plan.run_id,
        plan_id=run_plan.plan_id,
        planned=len(planned_ids),
        work_items=work_counts,
        trials=trial_counts,
        attempts=_attempt_counts(attempts),
        backend_submissions=_submission_counts(submissions),
        active_leases=sum(lease.state == "active" for lease in leases),
        expired_leases=sum(lease.state == "expired" for lease in leases),
        retries=sum(attempt.retry_number > 0 for attempt in attempts),
        started_at=started_at,
        last_activity_at=last_activity_at,
        estimated_remaining_work_count=(
            trial_counts.planned
            + trial_counts.queued
            + trial_counts.running
            + trial_counts.unknown
            + trial_counts.missing
        ),
        completion_blocked_by_non_terminal=non_terminal,
        completion_blocked_by_unknown=unknown,
        completion_blocked=non_terminal or unknown,
    )


def _trial_counts(planned_ids: tuple[UUID, ...], rows: dict[UUID, PlannedTrialRecord]) -> TrialProgressCounts:
    counts = Counter(row.state for row in rows.values())
    return TrialProgressCounts(
        planned=counts["planned"],
        queued=counts["queued"],
        running=counts["running"],
        succeeded=counts["succeeded"],
        failed=counts["failed"],
        cancelled=counts["cancelled"],
        invalid=counts["invalid"],
        unknown=counts["unknown"],
        missing=len(planned_ids) - len(rows),
    )


def _work_counts(planned_ids: tuple[UUID, ...], rows: dict[UUID, WorkItemRecord]) -> WorkItemProgressCounts:
    counts = Counter(row.state for row in rows.values())
    return WorkItemProgressCounts(
        planned=counts["planned"],
        queued=counts["queued"],
        leased=counts["leased"],
        running=counts["running"],
        cancel_requested=counts["cancel_requested"],
        succeeded=counts["succeeded"],
        failed=counts["failed"],
        cancelled=counts["cancelled"],
        invalid=counts["invalid"],
        unknown=counts["unknown"],
        missing=len(planned_ids) - len(rows),
    )


def _attempt_counts(records: tuple[AttemptRecord, ...]) -> AttemptProgressCounts:
    counts = Counter(record.state for record in records)
    return AttemptProgressCounts(
        created=counts["created"],
        submitted=counts["submitted"],
        running=counts["running"],
        succeeded=counts["succeeded"],
        failed=counts["failed"],
        cancelled=counts["cancelled"],
        unknown=counts["unknown"],
    )


def _submission_counts(records: tuple[BackendSubmissionRecord, ...]) -> BackendSubmissionProgressCounts:
    counts = Counter(record.state for record in records)
    return BackendSubmissionProgressCounts(
        submitted=counts["submitted"],
        accepted=counts["accepted"],
        running=counts["running"],
        completed=counts["completed"],
        failed=counts["failed"],
        unknown=counts["unknown"],
    )


def _validated_trial_rows(run_plan: RunPlan, rows: tuple[PlannedTrialRecord, ...]) -> dict[UUID, PlannedTrialRecord]:
    authoritative = {trial.trial_id: trial for trial in run_plan.trials}
    validated: dict[UUID, PlannedTrialRecord] = {}
    for row in rows:
        if row.run_id != str(run_plan.run_id):
            raise OperationalStoreError(
                f"operational trial {row.trial_id} belongs to run {row.run_id}, not authoritative run {run_plan.run_id}"
            )
        if row.plan_id != str(run_plan.plan_id):
            raise OperationalStoreError(
                f"operational trial {row.trial_id} belongs to plan {row.plan_id}, "
                f"not authoritative plan {run_plan.plan_id}"
            )
        trial_id = UUID(row.trial_id)
        trial = authoritative.get(trial_id)
        if trial is None:
            raise OperationalStoreError(
                f"operational trial {row.trial_id} is not present in authoritative run plan {run_plan.plan_id}"
            )
        if row.ordinal != trial.ordinal:
            raise OperationalStoreError(
                f"operational trial {row.trial_id} ordinal {row.ordinal} "
                f"does not match authoritative ordinal {trial.ordinal}"
            )
        validated[trial_id] = row
    return validated


__all__ = (
    "AttemptProgressCounts",
    "BackendSubmissionProgressCounts",
    "RunProgress",
    "TrialProgressCounts",
    "WorkItemProgressCounts",
    "project_run_progress",
)
