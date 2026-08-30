# ABOUTME: Provides the provider-neutral local bounded scheduler for PRD3 execution.
# ABOUTME: Selects queued work under explicit concurrency caps and leaves task execution to a caller.

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.execution_policy import ExecutionPolicy
from aec_bench.contracts.run_plan import RunPlan
from aec_bench.contracts.validators import FrozenStrictModel
from aec_bench.execution.models import TrialWorkItem
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


Worker = Callable[[WorkItemRecord, AttemptRecord], None]


class LocalScheduler:
    """Dispatches local work without interpreting task or evaluation semantics."""

    def __init__(self, store: OperationalStore, policy: ExecutionPolicy) -> None:
        self.store = store
        self.policy = policy

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
        running: list[tuple[WorkItemRecord, AttemptRecord, LeaseRecord]] = []
        for work_item, lease in leased:
            attempt = self.store.create_attempt_for_lease(
                work_item.work_id,
                trial_id=work_item.trial_id,
                lease_id=lease.lease_id,
                now=selected_now,
            )
            self.store.update_work_item(work_item.work_id, state="running", now=selected_now)
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
                    lease_lost = lease.lease_id in lost_leases
                    if lease_lost:
                        self.store.transition_attempt(attempt.attempt_id, state="unknown")
                        self.store.update_planned_trial(work_item.trial_id, state="unknown")
                        self.store.update_work_item(work_item.work_id, state="unknown")
                    else:
                        try:
                            future.result()
                        except Exception:
                            self.store.transition_attempt(attempt.attempt_id, state="failed")
                            self.store.update_planned_trial(work_item.trial_id, state="failed")
                            self.store.update_work_item(work_item.work_id, state="failed")
                            failed += 1
                        else:
                            self.store.transition_attempt(attempt.attempt_id, state="succeeded")
                            self.store.update_planned_trial(work_item.trial_id, state="succeeded")
                            self.store.update_work_item(work_item.work_id, state="succeeded")
                            succeeded += 1
                        try:
                            self.store.release_lease(lease.lease_id, owner=owner)
                        except OperationalStoreError:
                            if future.exception() is None:
                                succeeded -= 1
                            else:
                                failed -= 1
                            self.store.transition_attempt(attempt.attempt_id, state="unknown")
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
            idle=False,
        )


__all__ = ("LocalScheduler", "SchedulerRunReport", "Worker")
