# ABOUTME: Provides the provider-neutral local bounded scheduler for PRD3 execution.
# ABOUTME: Selects queued work under explicit concurrency caps and leaves task execution to a caller.

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.execution_policy import ExecutionPolicy
from aec_bench.contracts.run_plan import RunPlan
from aec_bench.contracts.validators import FrozenStrictModel
from aec_bench.execution.backend import ExecutionBackendControl
from aec_bench.execution.models import (
    BackendCancellationResult,
    FailureClass,
    FailureClassification,
    FailureKind,
    TrialWorkItem,
    WorkerOutcome,
)
from aec_bench.execution.operational import (
    AttemptRecord,
    LeaseRecord,
    OperationalStore,
    OperationalStoreError,
    QueueCount,
    WorkItemRecord,
)


class SchedulerRunReport(FrozenStrictModel):
    """Results from one bounded scheduler dispatch pass."""

    leased_count: PositiveInt | Literal[0] = 0
    succeeded_count: Annotated[int, Field(strict=True, ge=0)] = 0
    failed_count: Annotated[int, Field(strict=True, ge=0)] = 0
    retried_count: Annotated[int, Field(strict=True, ge=0)] = 0
    cancelled_count: Annotated[int, Field(strict=True, ge=0)] = 0
    unknown_count: Annotated[int, Field(strict=True, ge=0)] = 0
    idle: bool
    next_available_at: datetime | None = None

    @field_validator("next_available_at")
    @classmethod
    def validate_next_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("next_available_at must include a timezone")
        return None if value is None else value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.succeeded_count + self.failed_count > self.leased_count:
            raise ValueError("scheduler completion counts must not exceed leased count")
        if self.idle != (self.leased_count == 0):
            raise ValueError("scheduler idle flag must match leased count")
        return self


Worker = Callable[[WorkItemRecord, AttemptRecord], WorkerOutcome | None]


class LocalScheduler:
    """Dispatches local work without interpreting task or evaluation semantics."""

    def __init__(self, store: OperationalStore, policy: ExecutionPolicy) -> None:
        self.store = store
        self.policy = policy

    def request_cancellation(
        self, run_id: UUID | str, *, trial_id: UUID | str | None = None, now: datetime | None = None
    ) -> None:
        """Request cancellation and immediately stop future leasing for the target."""

        self.store.request_cancellation(run_id, trial_id=trial_id, now=now)

    def cancel_active(
        self,
        run_id: UUID | str,
        *,
        owner: str,
        backends: Mapping[str, ExecutionBackendControl],
        now: datetime | None = None,
    ) -> SchedulerRunReport:
        """Cancel active work through its backend and close only known outcomes."""

        selected_now = now or datetime.now(UTC)
        run = self.store.request_cancellation(run_id, now=selected_now)
        cancelled = 0
        unknown = 0
        for item in self.store.list_work_items(run.run_id):
            if item.state != "cancel_requested":
                continue
            attempts = self.store.list_attempts_for_work(item.work_id)
            if not attempts:
                continue
            attempt = attempts[-1]
            submissions = self.store.list_backend_submissions(attempt.attempt_id)
            submission = submissions[-1] if submissions else None
            backend = backends.get(item.backend)
            if submission is None:
                result = BackendCancellationResult(status="confirmed", message="no external submission exists")
            elif backend is None or not hasattr(backend, "cancel"):
                result = BackendCancellationResult(
                    status="unsupported", message="backend does not support cancellation"
                )
            else:
                try:
                    result = backend.cancel(item, attempt, submission)
                except Exception as error:
                    result = BackendCancellationResult(status="unknown", message=str(error))
            if result.status == "confirmed":
                self.store.transition_attempt(
                    attempt.attempt_id,
                    state="cancelled",
                    now=selected_now,
                    cancellation_status="confirmed",
                )
                if submission is not None:
                    self.store.transition_backend_submission(
                        submission.submission_id,
                        state="cancelled",
                        now=selected_now,
                        cancellation_status="confirmed",
                    )
                self.store.update_work_item(item.work_id, state="cancelled", now=selected_now)
                self.store.update_planned_trial(item.trial_id, state="cancelled", now=selected_now)
                cancelled += 1
            else:
                failure_kind = FailureKind.UNKNOWN_EXTERNAL_STATE
                failure = FailureClassification(
                    failure_class=FailureClass.UNKNOWN,
                    kind=failure_kind,
                    message=f"cancellation {result.status}: {result.message}",
                )
                self.store.transition_attempt(
                    attempt.attempt_id,
                    state="unknown",
                    now=selected_now,
                    failure=failure,
                    reconciliation_state="pending",
                    cancellation_status=result.status,
                )
                if submission is not None:
                    self.store.transition_backend_submission(
                        submission.submission_id,
                        state="unknown",
                        now=selected_now,
                        cancellation_status=result.status,
                        reconciliation_state="pending",
                    )
                self.store.update_work_item(item.work_id, state="unknown", now=selected_now)
                self.store.update_planned_trial(item.trial_id, state="unknown", now=selected_now)
                unknown += 1
            self.store.complete_plan_if_terminal(item.plan_id, run_id=item.run_id, now=selected_now)
            try:
                self.store.release_lease(
                    next(
                        lease.lease_id
                        for lease in self.store.list_leases_for_run(run.run_id)
                        if lease.work_id == item.work_id and lease.state == "active"
                    ),
                    owner=owner,
                    now=selected_now,
                )
            except (OperationalStoreError, StopIteration):
                pass
        return SchedulerRunReport(
            idle=True,
            cancelled_count=cancelled,
            unknown_count=unknown,
        )

    def reconcile_unknown(
        self,
        run_id: UUID | str,
        *,
        backends: Mapping[str, ExecutionBackendControl],
        now: datetime | None = None,
    ) -> SchedulerRunReport:
        """Reconcile unknown work before allowing any retry."""

        selected_now = now or datetime.now(UTC)
        resolved = 0
        unknown = 0
        retried = 0
        for item in self.store.list_work_items(run_id):
            if item.state != "unknown":
                continue
            attempts = self.store.list_attempts_for_work(item.work_id)
            submissions = () if not attempts else self.store.list_backend_submissions(attempts[-1].attempt_id)
            backend = backends.get(item.backend)
            if not attempts or not submissions or backend is None:
                unknown += 1
                continue
            try:
                outcome = backend.reconcile(item, attempts[-1], submissions[-1])
            except Exception:
                unknown += 1
                continue
            if outcome.terminal_state == "unknown":
                unknown += 1
                continue
            selected_receipt = next(
                (receipt for receipt in outcome.receipts if str(receipt.attempt_id) == attempts[-1].attempt_id), None
            )
            self.store.transition_attempt(
                attempts[-1].attempt_id,
                state=outcome.terminal_state,
                failure=None if selected_receipt is None else selected_receipt.failure,
                reconciliation_state="reconciled",
            )
            self.store.update_planned_trial(item.trial_id, state=outcome.terminal_state, now=selected_now)
            self.store.update_work_item(item.work_id, state=outcome.terminal_state, now=selected_now)
            if (
                outcome.terminal_state == "failed"
                and outcome.finalization is None
                and selected_receipt is not None
                and selected_receipt.failure is not None
            ):
                if self._schedule_retry(
                    item,
                    attempts[-1],
                    selected_receipt.failure,
                    selected_now,
                    after_unknown=True,
                ):
                    retried += 1
                    resolved += 1
                    continue
            resolved += 1
            self.store.complete_plan_if_terminal(item.plan_id, run_id=item.run_id, now=selected_now)
        return SchedulerRunReport(
            leased_count=0,
            retried_count=retried,
            unknown_count=unknown,
            idle=True,
        )

    def enqueue_ready_plan(self, run_plan: RunPlan, work_items: Sequence[TrialWorkItem]) -> tuple[WorkItemRecord, ...]:
        """Enqueue every trial in a ready plan exactly once."""

        if run_plan.state != "ready":
            raise OperationalStoreError("only ready run plans can be enqueued")
        plan_record = self.store.get_plan(run_plan.plan_id)
        if plan_record.run_id != str(run_plan.run_id):
            raise OperationalStoreError("stored plan does not belong to the authoritative run")
        if plan_record.state != "ready":
            raise OperationalStoreError("stored plan is not ready for enqueue")
        expected = {trial.trial_id: trial for trial in run_plan.trials}
        supplied = {item.trial_id: item for item in work_items}
        if set(supplied) != set(expected):
            raise OperationalStoreError("enqueue work items must cover each ready plan trial exactly once")
        if len(supplied) != len(work_items):
            raise OperationalStoreError("enqueue work items must not duplicate a trial")
        for trial_id, item in supplied.items():
            trial = expected[trial_id]
            if (
                item.run_id != run_plan.run_id
                or item.plan_id != run_plan.plan_id
                or item.ordinal != trial.ordinal
                or item.execution_family != trial.execution_family
                or item.retry_policy != self.policy.retry_policy
                or item.state not in {"planned", "queued"}
            ):
                raise OperationalStoreError(f"work item does not match authoritative trial: {trial_id}")
        for trial in run_plan.trials:
            self.store.put_planned_trial(
                trial.trial_id,
                plan_id=run_plan.plan_id,
                run_id=run_plan.run_id,
                ordinal=trial.ordinal,
            )
        records = tuple(
            self.store.create_work_item(
                item.work_id,
                work_key=str(item.work_key),
                run_id=item.run_id,
                trial_id=item.trial_id,
                kind="trial",
                priority=item.priority,
                plan_id=item.plan_id,
                ordinal=item.ordinal,
                execution_family=item.execution_family,
                backend=str(item.backend),
                provider_route=str(item.provider_route),
                model_route=str(item.model_route),
                resource_class=str(item.resource_class),
                available_at=item.available_at,
                retry_policy=item.retry_policy,
                now=item.created_at,
            )
            for item in sorted(work_items, key=lambda value: value.ordinal)
        )
        return records

    def queue_counts(self, run_id: UUID | str | None = None) -> tuple[QueueCount, ...]:
        """Return queue counts grouped by run, backend, and state."""

        return self.store.list_queue_counts(run_id)

    def dispatch_once(
        self,
        worker: Worker,
        *,
        owner: str,
        now: datetime | None = None,
    ) -> SchedulerRunReport:
        """Lease and execute one bounded batch, waiting for its workers to finish."""

        selected_now = now or datetime.now(UTC)
        lease_ttl = timedelta(seconds=self.policy.lease_ttl_seconds)
        leased: list[tuple[WorkItemRecord, LeaseRecord]] = []
        for _ in range(self.policy.max_concurrency):
            selected = self.store.lease_next_work_item(
                owner=owner,
                now=selected_now,
                ttl=lease_ttl,
                global_limit=self.policy.max_concurrency,
                run_limits=self.policy.run_limits,
                backend_limits=self.policy.backend_limits,
                provider_route_limits=self.policy.provider_route_limits,
                model_route_limits=self.policy.model_route_limits,
                resource_class_limits=self.policy.resource_class_limits,
                execution_family_limits=self.policy.execution_family_limits,
                priority_aging_seconds=self.policy.priority_aging_seconds,
            )
            if selected is None:
                break
            leased.append(selected)
        if not leased:
            return SchedulerRunReport(
                idle=True,
                next_available_at=self.store.next_available_at(now=selected_now),
            )

        run_ids = {work_item.run_id for work_item, _ in leased}
        plan_ids = {work_item.plan_id for work_item, _ in leased}
        for run_id in run_ids:
            self.store.update_run(run_id, status="running", now=selected_now)
        for plan_id in plan_ids:
            self.store.update_plan(plan_id, state="started", now=selected_now)

        succeeded = 0
        failed = 0
        retried = 0
        cancelled = 0
        unknown = 0
        running: list[tuple[WorkItemRecord, AttemptRecord, LeaseRecord]] = []
        for work_item, lease in leased:
            prior_attempts = self.store.list_attempts_for_work(work_item.work_id)
            retry_number = max((record.retry_number for record in prior_attempts), default=-1) + 1
            attempt = self.store.create_attempt_for_lease(
                work_item.work_id,
                trial_id=work_item.trial_id,
                lease_id=lease.lease_id,
                candidate_index=1,
                retry_number=retry_number,
                now=selected_now,
            )
            work_item = self.store.update_work_item(work_item.work_id, state="running", now=selected_now)
            self.store.update_planned_trial(work_item.trial_id, state="running", now=selected_now)
            attempt = self.store.transition_attempt(attempt.attempt_id, state="running", now=selected_now)
            running.append((work_item, attempt, lease))
        with ThreadPoolExecutor(max_workers=len(running), thread_name_prefix="aec-bench-local") as executor:
            futures = {
                executor.submit(worker, work_item, attempt): (work_item, attempt, lease)
                for work_item, attempt, lease in running
            }
            pending = set(futures)
            lost_leases: set[str] = set()
            while pending:
                done, pending = wait(pending, timeout=self.policy.lease_heartbeat_seconds)
                for future in done:
                    work_item, attempt, lease = futures[future]
                    current_state = self.store.get_work_item(work_item.work_id).state
                    if current_state in {"cancelled", "unknown"}:
                        if current_state == "unknown":
                            unknown += 1
                        try:
                            self.store.release_lease(lease.lease_id, owner=owner)
                        except OperationalStoreError:
                            pass
                        continue
                    lease_lost = lease.lease_id in lost_leases
                    if lease_lost:
                        self.store.transition_attempt(
                            attempt.attempt_id,
                            state="unknown",
                            failure=_unknown_failure("lease expired before worker completion"),
                            reconciliation_state="pending",
                        )
                        self.store.update_planned_trial(work_item.trial_id, state="unknown")
                        self.store.update_work_item(work_item.work_id, state="unknown")
                        unknown += 1
                    else:
                        try:
                            outcome = future.result()
                        except Exception:
                            current_attempt = self.store.get_attempt(attempt.attempt_id)
                            has_submission = bool(self.store.list_backend_submissions(attempt.attempt_id))
                            failure = _failure_from_record(current_attempt) or (
                                _unknown_failure("worker failed after backend submission")
                                if has_submission
                                else _infrastructure_failure(
                                    FailureKind.WORKER_LOST_BEFORE_SUBMISSION,
                                    "worker failed before backend submission",
                                )
                            )
                            terminal_state = (
                                "failed"
                                if current_attempt.state == "failed"
                                else ("unknown" if has_submission else "failed")
                            )
                            self.store.transition_attempt(
                                attempt.attempt_id,
                                state=terminal_state,
                                failure=failure,
                                reconciliation_state="pending" if has_submission else "not_required",
                            )
                            self.store.update_planned_trial(work_item.trial_id, state=terminal_state)
                            self.store.update_work_item(work_item.work_id, state=terminal_state)
                            if terminal_state == "unknown":
                                unknown += 1
                            elif self._schedule_retry(work_item, attempt, failure, selected_now):
                                retried += 1
                            else:
                                failed += 1
                        else:
                            if isinstance(outcome, WorkerOutcome):
                                terminal_state = outcome.terminal_state
                                selected_receipt = next(
                                    (
                                        receipt
                                        for receipt in outcome.receipts
                                        if str(receipt.attempt_id) == attempt.attempt_id
                                    ),
                                    None,
                                )
                                selected_failure: FailureClassification | None = (
                                    None if selected_receipt is None else selected_receipt.failure
                                )
                                finalizes_scheduler_attempt = (
                                    outcome.finalization is None
                                    or str(outcome.finalization.attempt_id) == attempt.attempt_id
                                )
                                if selected_receipt is not None and finalizes_scheduler_attempt:
                                    self.store.transition_attempt(
                                        attempt.attempt_id,
                                        state=terminal_state,
                                        failure=selected_failure,
                                        reconciliation_state=selected_receipt.reconciliation_status.value,
                                        cancellation_status=selected_receipt.cancellation_status.value,
                                    )
                                self.store.update_planned_trial(work_item.trial_id, state=terminal_state)
                                self.store.update_work_item(work_item.work_id, state=terminal_state)
                                if outcome.terminal_state == "succeeded":
                                    succeeded += 1
                                elif outcome.terminal_state == "failed":
                                    if (
                                        outcome.finalization is None
                                        and selected_failure is not None
                                        and self._schedule_retry(work_item, attempt, selected_failure, selected_now)
                                    ):
                                        retried += 1
                                    else:
                                        failed += 1
                                else:
                                    unknown += 1
                            else:
                                self.store.transition_attempt(attempt.attempt_id, state="succeeded")
                                self.store.update_planned_trial(work_item.trial_id, state="succeeded")
                                self.store.update_work_item(work_item.work_id, state="succeeded")
                                succeeded += 1
                        try:
                            self.store.release_lease(lease.lease_id, owner=owner)
                        except OperationalStoreError:
                            result_state = self.store.get_work_item(work_item.work_id).state
                            if result_state == "succeeded":
                                succeeded -= 1
                            elif result_state == "failed":
                                failed -= 1
                            elif result_state == "queued":
                                retried -= 1
                            if result_state != "unknown":
                                unknown += 1
                            self.store.transition_attempt(
                                attempt.attempt_id,
                                state="unknown",
                                failure=_unknown_failure("lease release status is unknown"),
                                reconciliation_state="pending",
                            )
                            self.store.update_planned_trial(work_item.trial_id, state="unknown")
                            self.store.update_work_item(work_item.work_id, state="unknown")
                    self.store.complete_plan_if_terminal(work_item.plan_id, run_id=work_item.run_id)
                if pending:
                    heartbeat_now = datetime.now(UTC)
                    for future in pending:
                        _, _, lease = futures[future]
                        if lease.lease_id in lost_leases:
                            continue
                        try:
                            self.store.renew_lease(
                                lease.lease_id,
                                owner=owner,
                                now=heartbeat_now,
                                ttl=lease_ttl,
                            )
                        except OperationalStoreError:
                            lost_leases.add(lease.lease_id)
        return SchedulerRunReport(
            leased_count=len(leased),
            succeeded_count=succeeded,
            failed_count=failed,
            retried_count=retried,
            cancelled_count=cancelled,
            unknown_count=unknown,
            idle=False,
        )

    def _schedule_retry(
        self,
        work_item: WorkItemRecord,
        attempt: AttemptRecord,
        failure: FailureClassification,
        now: datetime,
        *,
        after_unknown: bool = False,
    ) -> bool:
        policy = work_item.retry_policy
        if after_unknown and policy.unknown_state_policy == "never_retry":
            return False
        if (
            failure.failure_class is not FailureClass.INFRASTRUCTURE
            or failure.kind not in policy.retryable_failure_kinds
        ):
            return False
        attempts = self.store.list_attempts_for_work(work_item.work_id)
        next_retry = max((record.retry_number for record in attempts), default=-1) + 1
        if next_retry >= policy.maximum_attempts:
            return False
        if policy.maximum_elapsed_seconds is not None:
            first = min(record.created_at for record in attempts)
            next_available = now + timedelta(seconds=policy.backoff_seconds)
            if (next_available - first).total_seconds() > policy.maximum_elapsed_seconds:
                return False
        self.store.schedule_retry(
            work_item.work_id,
            available_at=now + timedelta(seconds=policy.backoff_seconds),
            now=now,
        )
        return True


__all__ = ("LocalScheduler", "SchedulerRunReport", "Worker")


def _infrastructure_failure(kind: FailureKind, message: str) -> FailureClassification:
    return FailureClassification(failure_class=FailureClass.INFRASTRUCTURE, kind=kind, message=message)


def _unknown_failure(message: str) -> FailureClassification:
    return FailureClassification(
        failure_class=FailureClass.UNKNOWN,
        kind=FailureKind.UNKNOWN_EXTERNAL_STATE,
        message=message,
    )


def _failure_from_record(attempt: AttemptRecord) -> FailureClassification | None:
    if attempt.failure_kind is None or attempt.failure_class is None or attempt.failure_message is None:
        return None
    return FailureClassification(
        failure_class=FailureClass(attempt.failure_class),
        kind=FailureKind(attempt.failure_kind),
        message=attempt.failure_message,
    )
