# ABOUTME: Stores mutable execution coordination state in a small SQLite database.
# ABOUTME: Keeps portable run plans and evidence files outside this operational store.

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import cast
from urllib.parse import quote
from uuid import UUID

from aec_bench.contracts.identity import (
    EntityKind,
    PortableRelativePath,
    new_entity_id,
    validate_entity_key,
    validate_uuidv7,
)
from aec_bench.execution.models import (
    FailureClassification,
    RetryPolicy,
)
from aec_bench.execution.operational.schema import SCHEMA_STATEMENTS, SCHEMA_VERSION


class OperationalStoreError(RuntimeError):
    """Base error for operational store failures."""


class OperationalStoreConflict(OperationalStoreError):
    """Raised when an immutable identity is written with different content."""


class OperationalStoreNotFound(OperationalStoreError):
    """Raised when a requested operational record does not exist."""


class LeaseUnavailable(OperationalStoreError):
    """Raised when another worker owns a non-expired lease."""


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    status: str
    spec_ref: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime
    cancellation_requested_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PlanRecord:
    plan_id: str
    run_id: str
    state: str
    plan_ref: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlannedTrialRecord:
    trial_id: str
    plan_id: str
    run_id: str
    ordinal: int
    state: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkItemRecord:
    work_id: str
    work_key: str
    run_id: str
    trial_id: str
    kind: str
    state: str
    priority: int
    created_at: datetime
    updated_at: datetime
    plan_id: str
    ordinal: int
    execution_family: str
    backend: str
    provider_route: str
    model_route: str
    resource_class: str
    available_at: datetime
    retry_policy: RetryPolicy


@dataclass(frozen=True, slots=True)
class QueueCount:
    """One queue count grouped by run, backend, and work state."""

    run_id: str
    backend: str
    state: str
    count: int


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    attempt_id: str
    work_id: str
    run_id: str
    trial_id: str
    attempt_number: int
    candidate_index: int
    retry_number: int
    lease_id: str | None
    state: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime
    failure_kind: str | None = None
    failure_class: str | None = None
    failure_message: str | None = None
    reconciliation_state: str = "not_required"
    cancellation_status: str = "not_requested"


@dataclass(frozen=True, slots=True)
class BackendSubmissionRecord:
    submission_id: str
    attempt_id: str
    backend: str
    external_id: str | None
    external_work_id: str | None
    state: str
    submitted_at: datetime
    updated_at: datetime
    cancellation_status: str = "not_requested"
    reconciliation_state: str = "not_required"


@dataclass(frozen=True, slots=True)
class LeaseRecord:
    lease_id: str
    work_id: str
    owner: str
    acquired_at: datetime
    expires_at: datetime
    heartbeat_at: datetime
    state: str
    released_at: datetime | None


class OperationalStore:
    """Short-transaction repository for mutable execution state."""

    def __init__(
        self,
        path: Path,
        *,
        application_version: str | None = None,
        read_only: bool = False,
        require_existing: bool = False,
    ) -> None:
        self.path = Path(path).expanduser().absolute()
        self.read_only = read_only or require_existing
        if read_only or require_existing:
            if self.path.is_symlink() or not self.path.is_file():
                raise OperationalStoreError("operational database must already be a regular file")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.application_version = _required_text(application_version or _installed_version(), "application_version")
        if read_only or require_existing:
            self._validate_existing_schema()
            self.read_only = read_only
        else:
            self._initialize_schema()

    @classmethod
    def open_read_only(cls, path: Path) -> OperationalStore:
        """Open an existing current-schema database without any write capability."""

        return cls(path, read_only=True)

    @classmethod
    def open_existing(cls, path: Path) -> OperationalStore:
        """Open an existing current-schema database for an explicit write operation."""

        return cls(path, require_existing=True)

    def schema_version(self) -> int:
        with self._connection() as connection:
            row = connection.execute("SELECT schema_version FROM operational_schema WHERE singleton = 1").fetchone()
        if row is None:
            raise OperationalStoreError("operational schema metadata is missing; recreate the local database")
        return int(row[0])

    def create_run(
        self, run_id: UUID | str, *, spec_ref: str, status: str = "created", now: datetime | None = None
    ) -> RunRecord:
        selected_id = _required_id(run_id, "run_id")
        selected_status = _checked_status(status, {"created", "ready", "running", "completed", "failed", "cancelled"})
        created_at = _aware(now or datetime.now(UTC), "now")
        selected_ref = _required_ref(spec_ref, "spec_ref")
        stamp = _timestamp(created_at)
        with self._connection(immediate=True) as connection:
            existing = connection.execute(
                "SELECT spec_ref, status FROM operational_runs WHERE run_id = ?", (selected_id,)
            ).fetchone()
            if existing is not None:
                if existing[0] != selected_ref:
                    raise OperationalStoreConflict(f"run identity already has different content: {selected_id}")
                return self._run_from_row(
                    connection.execute("SELECT * FROM operational_runs WHERE run_id = ?", (selected_id,)).fetchone()
                )
            connection.execute(
                "INSERT INTO operational_runs (run_id,status,spec_ref,created_at,updated_at) VALUES (?,?,?,?,?)",
                (selected_id, selected_status, selected_ref, stamp, stamp),
            )
            return self._run_from_row(
                connection.execute("SELECT * FROM operational_runs WHERE run_id = ?", (selected_id,)).fetchone()
            )

    def update_run(self, run_id: UUID | str, *, status: str, now: datetime | None = None) -> RunRecord:
        selected_id = _required_id(run_id, "run_id")
        selected_status = _checked_status(status, {"created", "ready", "running", "completed", "failed", "cancelled"})
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            self._require_row(connection, "operational_runs", "run_id", selected_id)
            started_at = stamp if selected_status == "running" else None
            finished_at = stamp if selected_status in {"completed", "failed", "cancelled"} else None
            connection.execute(
                "UPDATE operational_runs SET status = ?, started_at = COALESCE(started_at, ?), "
                "finished_at = COALESCE(finished_at, ?), updated_at = ? WHERE run_id = ?",
                (selected_status, started_at, finished_at, stamp, selected_id),
            )
            return self._run_from_row(
                connection.execute("SELECT * FROM operational_runs WHERE run_id = ?", (selected_id,)).fetchone()
            )

    def get_run(self, run_id: UUID | str) -> RunRecord:
        selected_id = _required_id(run_id, "run_id")
        with self._connection() as connection:
            return self._run_from_row(self._require_row(connection, "operational_runs", "run_id", selected_id))

    def request_cancellation(
        self, run_id: UUID | str, *, trial_id: UUID | str | None = None, now: datetime | None = None
    ) -> RunRecord:
        """Request idempotent run or trial cancellation and stop new leasing."""

        selected_run = _required_id(run_id, "run_id")
        selected_trial = None if trial_id is None else _required_id(trial_id, "trial_id")
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            run = self._require_row(connection, "operational_runs", "run_id", selected_run)
            if run[1] in {"completed", "failed", "cancelled"}:
                return self._run_from_row(run)
            if selected_trial is None:
                connection.execute(
                    "UPDATE operational_runs SET cancellation_requested_at = COALESCE(cancellation_requested_at, ?), "
                    "updated_at = ? WHERE run_id = ?",
                    (stamp, stamp, selected_run),
                )
                connection.execute(
                    "UPDATE operational_work_items SET state = CASE WHEN state = 'queued' THEN 'cancelled' "
                    "WHEN state IN ('leased', 'running') THEN 'cancel_requested' ELSE state END, updated_at = ? "
                    "WHERE run_id = ? AND state IN ('queued', 'leased', 'running')",
                    (stamp, selected_run),
                )
                connection.execute(
                    "UPDATE operational_planned_trials SET state = 'cancelled', updated_at = ? WHERE run_id = ? "
                    "AND state IN ('planned', 'queued')",
                    (stamp, selected_run),
                )
            else:
                trial = self._require_row(connection, "operational_planned_trials", "trial_id", selected_trial)
                if trial[2] != selected_run:
                    raise OperationalStoreConflict("trial belongs to a different run")
                connection.execute(
                    "UPDATE operational_work_items SET state = CASE WHEN state = 'queued' THEN 'cancelled' "
                    "WHEN state IN ('leased', 'running') THEN 'cancel_requested' ELSE state END, updated_at = ? "
                    "WHERE trial_id = ? AND state IN ('queued', 'leased', 'running')",
                    (stamp, selected_trial),
                )
                connection.execute(
                    "UPDATE operational_planned_trials SET state = 'cancelled', updated_at = ? "
                    "WHERE trial_id = ? AND state IN ('planned', 'queued')",
                    (stamp, selected_trial),
                )
            terminal = ("succeeded", "failed", "cancelled", "invalid")
            connection.execute(
                "UPDATE operational_plans SET state = 'closed', updated_at = ? WHERE run_id = ? AND "
                "NOT EXISTS (SELECT 1 FROM operational_planned_trials WHERE plan_id = operational_plans.plan_id "
                "AND state NOT IN (?,?,?,?)) AND NOT EXISTS (SELECT 1 FROM operational_work_items "
                "WHERE plan_id = operational_plans.plan_id AND state NOT IN (?,?,?,?))",
                (stamp, selected_run, *terminal, *terminal),
            )
            remaining = connection.execute(
                "SELECT COUNT(*) FROM operational_planned_trials WHERE run_id = ? AND state NOT IN (?,?,?,?)",
                (selected_run, *terminal),
            ).fetchone()[0]
            remaining += connection.execute(
                "SELECT COUNT(*) FROM operational_work_items WHERE run_id = ? AND state NOT IN (?,?,?,?)",
                (selected_run, *terminal),
            ).fetchone()[0]
            if remaining == 0:
                connection.execute(
                    "UPDATE operational_runs SET status = 'cancelled', finished_at = COALESCE(finished_at, ?), "
                    "updated_at = ? WHERE run_id = ?",
                    (stamp, stamp, selected_run),
                )
            return self._run_from_row(
                connection.execute("SELECT * FROM operational_runs WHERE run_id = ?", (selected_run,)).fetchone()
            )

    def put_plan(
        self,
        plan_id: UUID | str,
        *,
        run_id: UUID | str,
        plan_ref: str,
        state: str = "draft",
        now: datetime | None = None,
    ) -> PlanRecord:
        selected_plan = _required_id(plan_id, "plan_id")
        selected_run = _required_id(run_id, "run_id")
        selected_state = _checked_status(state, {"draft", "ready", "started", "closed"})
        selected_ref = _required_ref(plan_ref, "plan_ref")
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            self._require_row(connection, "operational_runs", "run_id", selected_run)
            existing = connection.execute(
                "SELECT * FROM operational_plans WHERE plan_id = ?", (selected_plan,)
            ).fetchone()
            if existing is not None:
                if existing[1] != selected_run or existing[3] != selected_ref:
                    raise OperationalStoreConflict(f"plan identity already has different content: {selected_plan}")
                return self._plan_from_row(existing)
            connection.execute(
                "INSERT INTO operational_plans "
                "(plan_id,run_id,state,plan_ref,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                (selected_plan, selected_run, selected_state, selected_ref, stamp, stamp),
            )
            return self._plan_from_row(
                connection.execute("SELECT * FROM operational_plans WHERE plan_id = ?", (selected_plan,)).fetchone()
            )

    def get_plan(self, plan_id: UUID | str) -> PlanRecord:
        selected_id = _required_id(plan_id, "plan_id")
        with self._connection() as connection:
            return self._plan_from_row(self._require_row(connection, "operational_plans", "plan_id", selected_id))

    def update_plan(self, plan_id: UUID | str, *, state: str, now: datetime | None = None) -> PlanRecord:
        """Transition one mutable operational plan state."""

        selected_id = _required_id(plan_id, "plan_id")
        selected_state = _checked_status(state, {"draft", "ready", "started", "closed"})
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            self._require_row(connection, "operational_plans", "plan_id", selected_id)
            connection.execute(
                "UPDATE operational_plans SET state = ?, updated_at = ? WHERE plan_id = ?",
                (selected_state, stamp, selected_id),
            )
            return self._plan_from_row(
                connection.execute("SELECT * FROM operational_plans WHERE plan_id = ?", (selected_id,)).fetchone()
            )

    def put_planned_trial(
        self,
        trial_id: UUID | str,
        *,
        plan_id: UUID | str,
        run_id: UUID | str,
        ordinal: int,
        state: str = "planned",
        now: datetime | None = None,
    ) -> PlannedTrialRecord:
        selected_trial = _required_id(trial_id, "trial_id")
        selected_plan = _required_id(plan_id, "plan_id")
        selected_run = _required_id(run_id, "run_id")
        if ordinal <= 0:
            raise ValueError("ordinal must be greater than zero")
        selected_state = _checked_status(
            state,
            {"planned", "queued", "running", "succeeded", "failed", "cancelled", "invalid", "unknown"},
        )
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            plan = self._require_row(connection, "operational_plans", "plan_id", selected_plan)
            self._require_row(connection, "operational_runs", "run_id", selected_run)
            if plan[1] != selected_run:
                raise OperationalStoreConflict("planned trial plan belongs to a different run")
            existing = connection.execute(
                "SELECT * FROM operational_planned_trials WHERE trial_id = ?", (selected_trial,)
            ).fetchone()
            if existing is not None:
                if existing[1:4] != (selected_plan, selected_run, ordinal):
                    raise OperationalStoreConflict(f"trial identity already has different content: {selected_trial}")
                return self._trial_from_row(existing)
            ordinal_owner = connection.execute(
                "SELECT trial_id FROM operational_planned_trials WHERE plan_id = ? AND ordinal = ?",
                (selected_plan, ordinal),
            ).fetchone()
            if ordinal_owner is not None:
                raise OperationalStoreConflict(
                    f"plan ordinal already belongs to another trial: {selected_plan} ordinal {ordinal}"
                )
            connection.execute(
                "INSERT INTO operational_planned_trials "
                "(trial_id,plan_id,run_id,ordinal,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (selected_trial, selected_plan, selected_run, ordinal, selected_state, stamp, stamp),
            )
            return self._trial_from_row(
                connection.execute(
                    "SELECT * FROM operational_planned_trials WHERE trial_id = ?", (selected_trial,)
                ).fetchone()
            )

    def get_planned_trial(self, trial_id: UUID | str) -> PlannedTrialRecord:
        selected_id = _required_id(trial_id, "trial_id")
        with self._connection() as connection:
            return self._trial_from_row(
                self._require_row(connection, "operational_planned_trials", "trial_id", selected_id)
            )

    def update_planned_trial(
        self, trial_id: UUID | str, *, state: str, now: datetime | None = None
    ) -> PlannedTrialRecord:
        """Transition one mutable operational planned-trial state."""

        selected_id = _required_id(trial_id, "trial_id")
        selected_state = _checked_status(
            state, {"planned", "queued", "running", "succeeded", "failed", "cancelled", "invalid", "unknown"}
        )
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            self._require_row(connection, "operational_planned_trials", "trial_id", selected_id)
            connection.execute(
                "UPDATE operational_planned_trials SET state = ?, updated_at = ? WHERE trial_id = ?",
                (selected_state, stamp, selected_id),
            )
            return self._trial_from_row(
                connection.execute(
                    "SELECT * FROM operational_planned_trials WHERE trial_id = ?", (selected_id,)
                ).fetchone()
            )

    def complete_plan_if_terminal(
        self, plan_id: UUID | str, *, run_id: UUID | str, now: datetime | None = None
    ) -> tuple[PlanRecord, RunRecord] | None:
        """Close the selected plan when terminal, and the run when all plans are terminal."""

        selected_plan = _required_id(plan_id, "plan_id")
        selected_run = _required_id(run_id, "run_id")
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        terminal_states = ("succeeded", "failed", "cancelled", "invalid")
        with self._connection(immediate=True) as connection:
            plan = self._require_row(connection, "operational_plans", "plan_id", selected_plan)
            if plan[1] != selected_run:
                raise OperationalStoreConflict("plan belongs to a different run")
            planned_count, non_terminal_trial_count = connection.execute(
                "SELECT COUNT(*), SUM(CASE WHEN state NOT IN (?,?,?,?) THEN 1 ELSE 0 END) "
                "FROM operational_planned_trials WHERE plan_id = ?",
                (*terminal_states, selected_plan),
            ).fetchone()
            work_count, non_terminal_count = connection.execute(
                "SELECT COUNT(*), SUM(CASE WHEN state NOT IN (?,?,?,?) THEN 1 ELSE 0 END) "
                "FROM operational_work_items WHERE plan_id = ?",
                (*terminal_states, selected_plan),
            ).fetchone()
            if (
                planned_count == 0
                or work_count != planned_count
                or (non_terminal_trial_count or 0) != 0
                or (non_terminal_count or 0) != 0
            ):
                return None
            connection.execute(
                "UPDATE operational_plans SET state = 'closed', updated_at = ? WHERE plan_id = ?",
                (stamp, selected_plan),
            )
            run_planned_count, run_non_terminal_trial_count = connection.execute(
                "SELECT COUNT(*), SUM(CASE WHEN state NOT IN (?,?,?,?) THEN 1 ELSE 0 END) "
                "FROM operational_planned_trials WHERE run_id = ?",
                (*terminal_states, selected_run),
            ).fetchone()
            run_work_count, run_non_terminal_count = connection.execute(
                "SELECT COUNT(*), SUM(CASE WHEN state NOT IN (?,?,?,?) THEN 1 ELSE 0 END) "
                "FROM operational_work_items WHERE run_id = ?",
                (*terminal_states, selected_run),
            ).fetchone()
            if (
                run_planned_count > 0
                and run_work_count == run_planned_count
                and (run_non_terminal_trial_count or 0) == 0
                and (run_non_terminal_count or 0) == 0
            ):
                run_status = (
                    "cancelled"
                    if connection.execute(
                        "SELECT cancellation_requested_at FROM operational_runs WHERE run_id = ?", (selected_run,)
                    ).fetchone()[0]
                    is not None
                    else "completed"
                )
                connection.execute(
                    f"UPDATE operational_runs SET status = '{run_status}', finished_at = COALESCE(finished_at, ?), "
                    "updated_at = ? WHERE run_id = ?",
                    (stamp, stamp, selected_run),
                )
            return (
                self._plan_from_row(
                    connection.execute("SELECT * FROM operational_plans WHERE plan_id = ?", (selected_plan,)).fetchone()
                ),
                self._run_from_row(
                    connection.execute("SELECT * FROM operational_runs WHERE run_id = ?", (selected_run,)).fetchone()
                ),
            )

    def create_work_item(
        self,
        work_id: UUID | str,
        *,
        work_key: str,
        run_id: UUID | str,
        trial_id: UUID | str,
        plan_id: UUID | str,
        ordinal: int,
        execution_family: str,
        backend: str,
        provider_route: str,
        model_route: str,
        resource_class: str,
        retry_policy: RetryPolicy,
        available_at: datetime,
        kind: str = "trial",
        priority: int = 0,
        now: datetime | None = None,
    ) -> WorkItemRecord:
        selected_id = _required_id(work_id, "work_id")
        selected_key = _required_key(work_key, "work_key")
        selected_run = _required_id(run_id, "run_id")
        selected_trial = _required_id(trial_id, "trial_id")
        selected_kind = _required_text(kind, "kind")
        selected_plan = _required_id(plan_id, "plan_id")
        if ordinal <= 0:
            raise ValueError("ordinal must be greater than zero")
        selected_family = _required_text(execution_family, "execution_family")
        selected_backend = _required_key(backend, "backend")
        selected_provider_route = _required_key(provider_route, "provider_route")
        selected_model_route = _required_key(model_route, "model_route")
        selected_resource_class = _required_key(resource_class, "resource_class")
        if not isinstance(retry_policy, RetryPolicy):
            raise TypeError("retry_policy must be a RetryPolicy")
        created_at = _aware(now or datetime.now(UTC), "now")
        available_at_value = _aware(available_at, "available_at")
        if available_at_value < created_at:
            raise ValueError("work item available_at must not precede created_at")
        stamp = _timestamp(created_at)
        available_stamp = _timestamp(available_at_value)
        retry_policy_json = json.dumps(retry_policy.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        with self._connection(immediate=True) as connection:
            self._require_row(connection, "operational_runs", "run_id", selected_run)
            trial = self._require_row(connection, "operational_planned_trials", "trial_id", selected_trial)
            plan = self._require_row(connection, "operational_plans", "plan_id", selected_plan)
            if plan[1] != selected_run or trial[1] != selected_plan or trial[2] != selected_run:
                raise OperationalStoreConflict("work item trial belongs to a different run")
            if int(trial[3]) != ordinal:
                raise OperationalStoreConflict("work item ordinal does not match planned trial")
            existing = connection.execute(
                "SELECT * FROM operational_work_items WHERE work_id = ?", (selected_id,)
            ).fetchone()
            if existing is not None:
                immutable = (
                    existing[1],
                    existing[2],
                    existing[3],
                    existing[4],
                    existing[6],
                    existing[9],
                    existing[10],
                    existing[11],
                    existing[12],
                    existing[13],
                    existing[14],
                    existing[15],
                    existing[16],
                    existing[17],
                )
                requested = (
                    selected_key,
                    selected_run,
                    selected_trial,
                    selected_kind,
                    priority,
                    selected_plan,
                    ordinal,
                    selected_family,
                    selected_backend,
                    selected_provider_route,
                    selected_model_route,
                    selected_resource_class,
                    available_stamp,
                    retry_policy_json,
                )
                if immutable != requested:
                    raise OperationalStoreConflict(f"work item identity already has different content: {selected_id}")
                return self._work_item_from_row(existing)
            trial_owner = connection.execute(
                "SELECT work_id FROM operational_work_items WHERE trial_id = ?", (selected_trial,)
            ).fetchone()
            if trial_owner is not None:
                raise OperationalStoreConflict(f"trial already belongs to another work item: {selected_trial}")
            key_owner = connection.execute(
                "SELECT work_id FROM operational_work_items WHERE run_id = ? AND work_key = ?",
                (selected_run, selected_key),
            ).fetchone()
            if key_owner is not None:
                raise OperationalStoreConflict(f"work key already belongs to another work item: {selected_key}")
            connection.execute(
                "INSERT INTO operational_work_items "
                "(work_id,work_key,run_id,trial_id,kind,state,priority,created_at,updated_at,plan_id,ordinal,"
                "execution_family,backend,provider_route,model_route,resource_class,available_at,retry_policy_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    selected_id,
                    selected_key,
                    selected_run,
                    selected_trial,
                    selected_kind,
                    "queued",
                    priority,
                    stamp,
                    stamp,
                    selected_plan,
                    ordinal,
                    selected_family,
                    selected_backend,
                    selected_provider_route,
                    selected_model_route,
                    selected_resource_class,
                    available_stamp,
                    retry_policy_json,
                ),
            )
            return self._work_item_from_row(
                connection.execute("SELECT * FROM operational_work_items WHERE work_id = ?", (selected_id,)).fetchone()
            )

    def update_work_item(
        self,
        work_id: UUID | str,
        *,
        state: str,
        available_at: datetime | None = None,
        now: datetime | None = None,
    ) -> WorkItemRecord:
        selected_id = _required_id(work_id, "work_id")
        selected_state = _checked_status(
            state,
            {
                "planned",
                "queued",
                "leased",
                "running",
                "cancel_requested",
                "succeeded",
                "failed",
                "cancelled",
                "invalid",
                "unknown",
            },
        )
        now_value = _aware(now or datetime.now(UTC), "now")
        stamp = _timestamp(now_value)
        with self._connection(immediate=True) as connection:
            work_item = self._require_row(connection, "operational_work_items", "work_id", selected_id)
            selected_available_at = None
            if available_at is not None:
                available_at_value = _aware(available_at, "available_at")
                if available_at_value < _parse_timestamp(work_item[7]):
                    raise ValueError("work item available_at must not precede created_at")
                selected_available_at = _timestamp(available_at_value)
            connection.execute(
                "UPDATE operational_work_items SET state = ?, updated_at = ?, available_at = "
                "COALESCE(?, available_at) WHERE work_id = ?",
                (selected_state, stamp, selected_available_at, selected_id),
            )
            return self._work_item_from_row(
                connection.execute("SELECT * FROM operational_work_items WHERE work_id = ?", (selected_id,)).fetchone()
            )

    def get_work_item(self, work_id: UUID | str) -> WorkItemRecord:
        selected_id = _required_id(work_id, "work_id")
        with self._connection() as connection:
            return self._work_item_from_row(
                self._require_row(connection, "operational_work_items", "work_id", selected_id)
            )

    def create_attempt(
        self,
        attempt_id: UUID | str,
        *,
        work_id: UUID | str,
        trial_id: UUID | str,
        attempt_number: int = 1,
        candidate_index: int,
        retry_number: int,
        lease_id: UUID | str | None = None,
        state: str = "created",
        now: datetime | None = None,
    ) -> AttemptRecord:
        selected_id = _required_id(attempt_id, "attempt_id")
        selected_work_item = _required_id(work_id, "work_id")
        selected_trial = _required_id(trial_id, "trial_id")
        selected_lease = None if lease_id is None else _required_id(lease_id, "lease_id")
        if attempt_number <= 0:
            raise ValueError("attempt_number must be greater than zero")
        if candidate_index <= 0:
            raise ValueError("candidate_index must be greater than zero")
        if retry_number < 0:
            raise ValueError("retry_number must not be negative")
        selected_state = _checked_status(
            state, {"created", "submitted", "running", "succeeded", "failed", "cancelled", "unknown"}
        )
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            item = self._require_row(connection, "operational_work_items", "work_id", selected_work_item)
            trial = self._require_row(connection, "operational_planned_trials", "trial_id", selected_trial)
            if item[3] != selected_trial or trial[2] != item[2]:
                raise OperationalStoreConflict("attempt work item and trial do not match")
            if selected_lease is not None:
                lease = self._require_row(connection, "operational_leases", "lease_id", selected_lease)
                if lease[1] != selected_work_item:
                    raise OperationalStoreConflict("attempt lease belongs to a different work item")
                if lease[6] != "active":
                    raise OperationalStoreConflict("attempt lease is not active")
                if _parse_timestamp(lease[4]) <= _parse_timestamp(stamp):
                    raise OperationalStoreConflict("attempt lease has expired")
            existing = connection.execute(
                "SELECT * FROM operational_attempts WHERE attempt_id = ?", (selected_id,)
            ).fetchone()
            if existing is not None:
                immutable = (existing[1], existing[3], existing[4], existing[5], existing[6], existing[7])
                if immutable != (
                    selected_work_item,
                    selected_trial,
                    attempt_number,
                    candidate_index,
                    retry_number,
                    selected_lease,
                ):
                    raise OperationalStoreConflict(f"attempt identity already has different content: {selected_id}")
                return self._attempt_from_row(existing)
            number_owner = connection.execute(
                "SELECT attempt_id FROM operational_attempts WHERE work_id = ? AND attempt_number = ?",
                (selected_work_item, attempt_number),
            ).fetchone()
            if number_owner is not None:
                raise OperationalStoreConflict(
                    f"attempt number already belongs to another attempt: {selected_work_item} attempt {attempt_number}"
                )
            connection.execute(
                "INSERT INTO operational_attempts "
                "(attempt_id,work_id,run_id,trial_id,attempt_number,candidate_index,retry_number,lease_id,state,"
                "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    selected_id,
                    selected_work_item,
                    item[2],
                    selected_trial,
                    attempt_number,
                    candidate_index,
                    retry_number,
                    selected_lease,
                    selected_state,
                    stamp,
                    stamp,
                ),
            )
            return self._attempt_from_row(
                connection.execute("SELECT * FROM operational_attempts WHERE attempt_id = ?", (selected_id,)).fetchone()
            )

    def get_attempt(self, attempt_id: UUID | str) -> AttemptRecord:
        selected_id = _required_id(attempt_id, "attempt_id")
        with self._connection() as connection:
            return self._attempt_from_row(
                self._require_row(connection, "operational_attempts", "attempt_id", selected_id)
            )

    def create_attempt_for_lease(
        self,
        work_id: UUID | str,
        *,
        trial_id: UUID | str,
        lease_id: UUID | str,
        candidate_index: int,
        retry_number: int,
        now: datetime | None = None,
    ) -> AttemptRecord:
        """Create the next attempt for an active lease in one transaction."""

        selected_work_item = _required_id(work_id, "work_id")
        selected_trial = _required_id(trial_id, "trial_id")
        selected_lease = _required_id(lease_id, "lease_id")
        selected_now = _aware(now or datetime.now(UTC), "now")
        if candidate_index <= 0:
            raise ValueError("candidate_index must be greater than zero")
        if retry_number < 0:
            raise ValueError("retry_number must not be negative")
        stamp = _timestamp(selected_now)
        with self._connection(immediate=True) as connection:
            item = self._require_row(connection, "operational_work_items", "work_id", selected_work_item)
            trial = self._require_row(connection, "operational_planned_trials", "trial_id", selected_trial)
            if item[3] != selected_trial or trial[2] != item[2]:
                raise OperationalStoreConflict("attempt work item and trial do not match")
            lease = self._require_row(connection, "operational_leases", "lease_id", selected_lease)
            if lease[1] != selected_work_item:
                raise OperationalStoreConflict("attempt lease belongs to a different work item")
            if lease[6] != "active" or _parse_timestamp(lease[4]) <= selected_now:
                raise OperationalStoreConflict("attempt lease is not active")
            row = connection.execute(
                "SELECT COALESCE(MAX(attempt_number), 0) + 1 FROM operational_attempts WHERE work_id = ?",
                (selected_work_item,),
            ).fetchone()
            attempt_number = int(row[0])
            attempt_id = str(new_entity_id(EntityKind.ATTEMPT))
            connection.execute(
                "INSERT INTO operational_attempts "
                "(attempt_id,work_id,run_id,trial_id,attempt_number,candidate_index,retry_number,lease_id,state,"
                "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    attempt_id,
                    selected_work_item,
                    item[2],
                    selected_trial,
                    attempt_number,
                    candidate_index,
                    retry_number,
                    selected_lease,
                    "created",
                    stamp,
                    stamp,
                ),
            )
            return self._attempt_from_row(
                connection.execute("SELECT * FROM operational_attempts WHERE attempt_id = ?", (attempt_id,)).fetchone()
            )

    def transition_attempt(
        self,
        attempt_id: UUID | str,
        *,
        state: str,
        now: datetime | None = None,
        failure: FailureClassification | None = None,
        reconciliation_state: str | None = None,
        cancellation_status: str | None = None,
    ) -> AttemptRecord:
        """Set an attempt state and record truthful running or terminal timestamps."""

        selected_id = _required_id(attempt_id, "attempt_id")
        selected_state = _checked_status(
            state, {"created", "submitted", "running", "succeeded", "failed", "cancelled", "unknown"}
        )
        selected_now = _aware(now or datetime.now(UTC), "now")
        stamp = _timestamp(selected_now)
        with self._connection(immediate=True) as connection:
            current = self._require_row(connection, "operational_attempts", "attempt_id", selected_id)
            started_at = stamp if selected_state == "running" else current[10]
            finished_at = stamp if selected_state in {"succeeded", "failed", "cancelled", "unknown"} else current[11]
            selected_reconciliation = reconciliation_state or current[16]
            selected_cancellation = cancellation_status or current[17]
            clear_failure = selected_state in {"succeeded", "cancelled"}
            failure_kind = None if failure is None else failure.kind.value
            failure_class = None if failure is None else failure.failure_class.value
            failure_message = None if failure is None else failure.message
            connection.execute(
                "UPDATE operational_attempts SET state = ?, started_at = ?, finished_at = ?, updated_at = ?, "
                "failure_kind = ?, failure_class = ?, failure_message = ?, reconciliation_state = ?, "
                "cancellation_status = ? "
                "WHERE attempt_id = ?",
                (
                    selected_state,
                    started_at,
                    finished_at,
                    stamp,
                    None if clear_failure else failure_kind or current[13],
                    None if clear_failure else failure_class or current[14],
                    None if clear_failure else failure_message or current[15],
                    selected_reconciliation,
                    selected_cancellation,
                    selected_id,
                ),
            )
            return self._attempt_from_row(
                connection.execute("SELECT * FROM operational_attempts WHERE attempt_id = ?", (selected_id,)).fetchone()
            )

    def record_backend_submission(
        self,
        submission_id: UUID | str,
        *,
        attempt_id: UUID | str,
        backend: str,
        external_id: str | None = None,
        external_work_id: str | None = None,
        state: str = "submitted",
        now: datetime | None = None,
    ) -> BackendSubmissionRecord:
        selected_id = _required_id(submission_id, "submission_id")
        selected_attempt = _required_id(attempt_id, "attempt_id")
        selected_backend = _required_text(backend, "backend")
        selected_external_id = None if external_id is None else _required_text(external_id, "external_id")
        selected_external_work_id = (
            None if external_work_id is None else _required_text(external_work_id, "external_work_id")
        )
        selected_state = _checked_status(
            state, {"submitted", "accepted", "running", "completed", "failed", "cancelled", "unknown"}
        )
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            self._require_row(connection, "operational_attempts", "attempt_id", selected_attempt)
            existing = connection.execute(
                "SELECT * FROM operational_backend_submissions WHERE submission_id = ?", (selected_id,)
            ).fetchone()
            if existing is not None:
                immutable = (existing[1], existing[2], existing[3], existing[4])
                if immutable != (selected_attempt, selected_backend, selected_external_id, selected_external_work_id):
                    raise OperationalStoreConflict(f"submission identity already has different content: {selected_id}")
                return self._submission_from_row(existing)
            backend_owner = connection.execute(
                "SELECT submission_id FROM operational_backend_submissions WHERE attempt_id = ? AND backend = ?",
                (selected_attempt, selected_backend),
            ).fetchone()
            if backend_owner is not None:
                raise OperationalStoreConflict(
                    f"backend already has another submission for attempt: {selected_attempt} backend {selected_backend}"
                )
            connection.execute(
                "INSERT INTO operational_backend_submissions "
                "(submission_id,attempt_id,backend,external_id,external_work_id,state,submitted_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    selected_id,
                    selected_attempt,
                    selected_backend,
                    selected_external_id,
                    selected_external_work_id,
                    selected_state,
                    stamp,
                    stamp,
                ),
            )
            return self._submission_from_row(
                connection.execute(
                    "SELECT * FROM operational_backend_submissions WHERE submission_id = ?", (selected_id,)
                ).fetchone()
            )

    def transition_backend_submission(
        self,
        submission_id: UUID | str,
        *,
        state: str,
        now: datetime | None = None,
        cancellation_status: str | None = None,
        reconciliation_state: str | None = None,
    ) -> BackendSubmissionRecord:
        """Record the observed state of one backend submission."""

        selected_id = _required_id(submission_id, "submission_id")
        selected_state = _checked_status(
            state, {"submitted", "accepted", "running", "completed", "failed", "cancelled", "unknown"}
        )
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            self._require_row(connection, "operational_backend_submissions", "submission_id", selected_id)
            connection.execute(
                "UPDATE operational_backend_submissions SET state = ?, updated_at = ?, cancellation_status = "
                "COALESCE(?, cancellation_status), reconciliation_state = COALESCE(?, reconciliation_state) "
                "WHERE submission_id = ?",
                (selected_state, stamp, cancellation_status, reconciliation_state, selected_id),
            )
            return self._submission_from_row(
                connection.execute(
                    "SELECT * FROM operational_backend_submissions WHERE submission_id = ?", (selected_id,)
                ).fetchone()
            )

    def bind_backend_submission_external_ids(
        self,
        submission_id: UUID | str,
        *,
        external_id: str,
        external_work_id: str | None = None,
        now: datetime | None = None,
    ) -> BackendSubmissionRecord:
        """Bind provider identifiers after a submission is accepted."""

        selected_id = _required_id(submission_id, "submission_id")
        selected_external_id = _required_text(external_id, "external_id")
        selected_external_work_id = (
            None if external_work_id is None else _required_text(external_work_id, "external_work_id")
        )
        stamp = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            current = self._require_row(connection, "operational_backend_submissions", "submission_id", selected_id)
            if current[3] is not None and current[3] != selected_external_id:
                raise OperationalStoreConflict(f"submission already has a different external ID: {selected_id}")
            if current[4] is not None and current[4] != selected_external_work_id:
                raise OperationalStoreConflict(f"submission already has a different external work ID: {selected_id}")
            owner = connection.execute(
                "SELECT submission_id FROM operational_backend_submissions "
                "WHERE external_id = ? AND submission_id != ?",
                (selected_external_id, selected_id),
            ).fetchone()
            if owner is not None:
                raise OperationalStoreConflict(
                    f"external ID already belongs to another submission: {selected_external_id}"
                )
            connection.execute(
                "UPDATE operational_backend_submissions SET external_id = ?, external_work_id = ?, updated_at = ? "
                "WHERE submission_id = ?",
                (selected_external_id, selected_external_work_id, stamp, selected_id),
            )
            return self._submission_from_row(
                connection.execute(
                    "SELECT * FROM operational_backend_submissions WHERE submission_id = ?", (selected_id,)
                ).fetchone()
            )

    def get_backend_submission(self, submission_id: UUID | str) -> BackendSubmissionRecord:
        selected_id = _required_id(submission_id, "submission_id")
        with self._connection() as connection:
            return self._submission_from_row(
                self._require_row(connection, "operational_backend_submissions", "submission_id", selected_id)
            )

    def list_planned_trials(self, plan_id: UUID | str) -> tuple[PlannedTrialRecord, ...]:
        selected_id = _required_id(plan_id, "plan_id")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM operational_planned_trials WHERE plan_id = ? ORDER BY ordinal", (selected_id,)
            ).fetchall()
        return tuple(self._trial_from_row(row) for row in rows)

    def list_work_items(self, run_id: UUID | str) -> tuple[WorkItemRecord, ...]:
        selected_id = _required_id(run_id, "run_id")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM operational_work_items "
                "WHERE run_id = ? ORDER BY priority DESC, created_at, ordinal, work_id",
                (selected_id,),
            ).fetchall()
        return tuple(self._work_item_from_row(row) for row in rows)

    def list_queue_counts(self, run_id: UUID | str | None = None) -> tuple[QueueCount, ...]:
        """Return queue counts grouped by run, backend, and state."""

        selected_id = None if run_id is None else _required_id(run_id, "run_id")
        with self._connection() as connection:
            if selected_id is None:
                rows = connection.execute(
                    "SELECT run_id, backend, state, COUNT(*) FROM operational_work_items "
                    "GROUP BY run_id, backend, state ORDER BY run_id, backend, state"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT run_id, backend, state, COUNT(*) FROM operational_work_items "
                    "WHERE run_id = ? GROUP BY run_id, backend, state ORDER BY run_id, backend, state",
                    (selected_id,),
                ).fetchall()
        return tuple(QueueCount(row[0], row[1], row[2], int(row[3])) for row in rows)

    def next_available_at(self, *, now: datetime, run_id: UUID | str | None = None) -> datetime | None:
        """Return the next future queue time without waiting or mutating state."""

        selected_now = _timestamp(_aware(now, "now"))
        selected_id = None if run_id is None else _required_id(run_id, "run_id")
        with self._connection() as connection:
            if selected_id is None:
                row = connection.execute(
                    "SELECT MIN(available_at) FROM operational_work_items WHERE state = 'queued' AND available_at > ?",
                    (selected_now,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT MIN(available_at) FROM operational_work_items "
                    "WHERE run_id = ? AND state = 'queued' AND available_at > ?",
                    (selected_id, selected_now),
                ).fetchone()
        return None if row is None or row[0] is None else _parse_timestamp(row[0])

    def list_attempts(self, trial_id: UUID | str) -> tuple[AttemptRecord, ...]:
        selected_id = _required_id(trial_id, "trial_id")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM operational_attempts WHERE trial_id = ? ORDER BY attempt_number, attempt_id",
                (selected_id,),
            ).fetchall()
        return tuple(self._attempt_from_row(row) for row in rows)

    def list_attempts_for_work(self, work_id: UUID | str) -> tuple[AttemptRecord, ...]:
        """Return attempts for one work item in creation order."""

        selected_id = _required_id(work_id, "work_id")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM operational_attempts WHERE work_id = ? ORDER BY attempt_number, attempt_id",
                (selected_id,),
            ).fetchall()
        return tuple(self._attempt_from_row(row) for row in rows)

    def schedule_retry(
        self, work_id: UUID | str, *, available_at: datetime, now: datetime | None = None
    ) -> WorkItemRecord:
        """Return failed work to the queue at an explicit backoff time."""

        selected_id = _required_id(work_id, "work_id")
        now_value = _aware(now or datetime.now(UTC), "now")
        available_value = _aware(available_at, "available_at")
        if available_value < now_value:
            raise ValueError("retry available_at must not precede now")
        stamp = _timestamp(now_value)
        with self._connection(immediate=True) as connection:
            item = self._require_row(connection, "operational_work_items", "work_id", selected_id)
            run = self._require_row(connection, "operational_runs", "run_id", item[2])
            if run[7] is not None:
                raise OperationalStoreConflict("cannot retry work after cancellation was requested")
            connection.execute(
                "UPDATE operational_work_items SET state = 'queued', available_at = ?, updated_at = ? "
                "WHERE work_id = ? AND state IN ('failed', 'unknown', 'cancel_requested')",
                (_timestamp(available_value), stamp, selected_id),
            )
            connection.execute(
                "UPDATE operational_planned_trials SET state = 'queued', updated_at = ? WHERE trial_id = ? "
                "AND state IN ('failed', 'unknown')",
                (stamp, item[3]),
            )
            return self._work_item_from_row(
                connection.execute("SELECT * FROM operational_work_items WHERE work_id = ?", (selected_id,)).fetchone()
            )

    def list_attempts_for_run(self, run_id: UUID | str) -> tuple[AttemptRecord, ...]:
        """Return all attempts for one run in stable trial and attempt order."""

        selected_id = _required_id(run_id, "run_id")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM operational_attempts WHERE run_id = ? ORDER BY trial_id, attempt_number, attempt_id",
                (selected_id,),
            ).fetchall()
        return tuple(self._attempt_from_row(row) for row in rows)

    def list_backend_submissions(self, attempt_id: UUID | str) -> tuple[BackendSubmissionRecord, ...]:
        selected_id = _required_id(attempt_id, "attempt_id")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM operational_backend_submissions "
                "WHERE attempt_id = ? ORDER BY submitted_at, submission_id",
                (selected_id,),
            ).fetchall()
        return tuple(self._submission_from_row(row) for row in rows)

    def list_backend_submissions_for_run(self, run_id: UUID | str) -> tuple[BackendSubmissionRecord, ...]:
        """Return all backend submissions for one run in stable identity order."""

        selected_id = _required_id(run_id, "run_id")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT submissions.* FROM operational_backend_submissions AS submissions "
                "JOIN operational_attempts AS attempts ON attempts.attempt_id = submissions.attempt_id "
                "WHERE attempts.run_id = ? ORDER BY submissions.submitted_at, submissions.submission_id",
                (selected_id,),
            ).fetchall()
        return tuple(self._submission_from_row(row) for row in rows)

    def get_lease(self, lease_id: UUID | str) -> LeaseRecord:
        selected_id = _required_id(lease_id, "lease_id")
        with self._connection() as connection:
            return self._lease_from_row(self._require_row(connection, "operational_leases", "lease_id", selected_id))

    def list_leases_for_run(self, run_id: UUID | str) -> tuple[LeaseRecord, ...]:
        """Return all leases for one run in stable acquisition order."""

        selected_id = _required_id(run_id, "run_id")
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT leases.* FROM operational_leases AS leases "
                "JOIN operational_work_items AS work_items ON work_items.work_id = leases.work_id "
                "WHERE work_items.run_id = ? ORDER BY leases.acquired_at, leases.lease_id",
                (selected_id,),
            ).fetchall()
        return tuple(self._lease_from_row(row) for row in rows)

    def lease_next_work_item(
        self,
        *,
        owner: str,
        now: datetime,
        ttl: timedelta,
        global_limit: int | None = None,
        run_limits: Mapping[str, int] | None = None,
        backend_limits: Mapping[str, int] | None = None,
        provider_route_limits: Mapping[str, int] | None = None,
        model_route_limits: Mapping[str, int] | None = None,
        resource_class_limits: Mapping[str, int] | None = None,
        execution_family_limits: Mapping[str, int] | None = None,
        priority_aging_seconds: int = 300,
        lease_id: UUID | str | None = None,
    ) -> tuple[WorkItemRecord, LeaseRecord] | None:
        """Lease one eligible work item while enforcing all active concurrency caps."""

        selected_owner = _required_text(owner, "owner")
        selected_now = _aware(now, "now")
        if ttl <= timedelta(0):
            raise ValueError("lease ttl must be greater than zero")
        if global_limit is not None and global_limit <= 0:
            raise ValueError("global_limit must be positive")
        if priority_aging_seconds <= 0:
            raise ValueError("priority_aging_seconds must be positive")
        selected_limits = {
            "run_limits": _checked_limits(run_limits),
            "backend_limits": _checked_limits(backend_limits),
            "provider_route_limits": _checked_limits(provider_route_limits),
            "model_route_limits": _checked_limits(model_route_limits),
            "resource_class_limits": _checked_limits(resource_class_limits),
            "execution_family_limits": _checked_limits(execution_family_limits),
        }
        selected_lease_id = _required_id(lease_id or _new_id(EntityKind.LEASE), "lease_id")
        acquired = _timestamp(selected_now)
        expires = _timestamp(selected_now + ttl)
        with self._connection(immediate=True) as connection:
            self._expire_leases(connection, acquired)
            active_rows = connection.execute(
                "SELECT work_items.* FROM operational_work_items AS work_items "
                "JOIN operational_leases AS leases ON leases.work_id = work_items.work_id "
                "WHERE leases.state = 'active'"
            ).fetchall()
            candidates = connection.execute(
                "SELECT work_items.* FROM operational_work_items AS work_items "
                "JOIN operational_runs AS runs ON runs.run_id = work_items.run_id "
                "WHERE work_items.state = 'queued' AND work_items.available_at <= ? "
                "AND runs.cancellation_requested_at IS NULL "
                "ORDER BY available_at, created_at, ordinal, work_id",
                (acquired,),
            ).fetchall()
            candidates = sorted(
                candidates,
                key=lambda row: _work_item_priority_key(row, selected_now, priority_aging_seconds),
            )
            active_global_count = len(active_rows)
            active_counts = {
                "run": _count_values(active_rows, 2),
                "backend": _count_values(active_rows, 12),
                "provider_route": _count_values(active_rows, 13),
                "model_route": _count_values(active_rows, 14),
                "resource_class": _count_values(active_rows, 15),
                "execution_family": _count_values(active_rows, 11),
            }
            for candidate in candidates:
                if global_limit is not None and active_global_count >= global_limit:
                    break
                if not _under_limit(candidate[2], selected_limits["run_limits"], active_counts["run"]):
                    continue
                if not _under_limit(candidate[12], selected_limits["backend_limits"], active_counts["backend"]):
                    continue
                if not _under_limit(
                    candidate[13], selected_limits["provider_route_limits"], active_counts["provider_route"]
                ):
                    continue
                if not _under_limit(candidate[14], selected_limits["model_route_limits"], active_counts["model_route"]):
                    continue
                if not _under_limit(
                    candidate[15], selected_limits["resource_class_limits"], active_counts["resource_class"]
                ):
                    continue
                if not _under_limit(
                    candidate[11], selected_limits["execution_family_limits"], active_counts["execution_family"]
                ):
                    continue
                connection.execute(
                    "INSERT INTO operational_leases "
                    "(lease_id,work_id,owner,acquired_at,expires_at,heartbeat_at,state) "
                    "VALUES (?,?,?,?,?,?,'active')",
                    (selected_lease_id, candidate[0], selected_owner, acquired, expires, acquired),
                )
                connection.execute(
                    "UPDATE operational_work_items SET state = 'leased', updated_at = ? WHERE work_id = ?",
                    (acquired, candidate[0]),
                )
                work_row = connection.execute(
                    "SELECT * FROM operational_work_items WHERE work_id = ?", (candidate[0],)
                ).fetchone()
                lease_row = connection.execute(
                    "SELECT * FROM operational_leases WHERE lease_id = ?", (selected_lease_id,)
                ).fetchone()
                if work_row is None or lease_row is None:
                    raise OperationalStoreError("leased work item disappeared before repository read")
                return self._work_item_from_row(work_row), self._lease_from_row(lease_row)
        return None

    def acquire_lease(
        self, work_id: UUID | str, *, owner: str, now: datetime, ttl: timedelta, lease_id: UUID | str | None = None
    ) -> LeaseRecord:
        selected_work_item = _required_id(work_id, "work_id")
        selected_owner = _required_text(owner, "owner")
        if ttl <= timedelta(0):
            raise ValueError("lease ttl must be greater than zero")
        selected_now = _aware(now, "now")
        selected_lease_id = _required_id(lease_id or _new_id(EntityKind.LEASE), "lease_id")
        acquired = _timestamp(selected_now)
        expires = _timestamp(selected_now + ttl)
        unavailable_reason: str | None = None
        acquired_lease: LeaseRecord | None = None
        with self._connection(immediate=True) as connection:
            self._expire_leases(connection, acquired)
            work_item = self._require_row(connection, "operational_work_items", "work_id", selected_work_item)
            existing = connection.execute(
                "SELECT * FROM operational_leases WHERE work_id = ? AND state = 'active'", (selected_work_item,)
            ).fetchone()
            if existing is not None and _parse_timestamp(existing[4]) > selected_now:
                unavailable_reason = f"work item lease is held by {existing[2]}"
            elif existing is None and work_item[5] != "queued":
                unavailable_reason = "work item is not queued"
            elif existing is not None:
                connection.execute(
                    "UPDATE operational_leases SET state = 'expired', released_at = expires_at WHERE lease_id = ?",
                    (existing[0],),
                )
            if unavailable_reason is None:
                connection.execute(
                    "INSERT INTO operational_leases "
                    "(lease_id,work_id,owner,acquired_at,expires_at,heartbeat_at,state) VALUES (?,?,?,?,?,?,'active')",
                    (selected_lease_id, selected_work_item, selected_owner, acquired, expires, acquired),
                )
                connection.execute(
                    "UPDATE operational_work_items SET state = 'leased', updated_at = ? WHERE work_id = ?",
                    (acquired, selected_work_item),
                )
                acquired_lease = self._lease_from_row(
                    connection.execute(
                        "SELECT * FROM operational_leases WHERE lease_id = ?", (selected_lease_id,)
                    ).fetchone()
                )
        if unavailable_reason is not None:
            raise LeaseUnavailable(unavailable_reason)
        if acquired_lease is None:
            raise OperationalStoreError("lease acquisition completed without a lease record")
        return acquired_lease

    def renew_lease(self, lease_id: UUID | str, *, owner: str, now: datetime, ttl: timedelta) -> LeaseRecord:
        selected_id = _required_id(lease_id, "lease_id")
        selected_owner = _required_text(owner, "owner")
        selected_now = _aware(now, "now")
        if ttl <= timedelta(0):
            raise ValueError("lease ttl must be greater than zero")
        with self._connection(immediate=True) as connection:
            lease = self._lease_from_row(self._require_row(connection, "operational_leases", "lease_id", selected_id))
            if lease.state != "active":
                raise LeaseUnavailable("lease is not active")
            if lease.owner != selected_owner:
                raise LeaseUnavailable("lease owner does not match")
            if lease.expires_at <= selected_now:
                raise LeaseUnavailable("lease has expired")
            connection.execute(
                "UPDATE operational_leases SET expires_at = ?, heartbeat_at = ? "
                "WHERE lease_id = ? AND state = 'active'",
                (_timestamp(selected_now + ttl), _timestamp(selected_now), selected_id),
            )
            return self._lease_from_row(
                connection.execute("SELECT * FROM operational_leases WHERE lease_id = ?", (selected_id,)).fetchone()
            )

    def release_lease(self, lease_id: UUID | str, *, owner: str, now: datetime | None = None) -> LeaseRecord:
        selected_id = _required_id(lease_id, "lease_id")
        selected_owner = _required_text(owner, "owner")
        released_at = _timestamp(_aware(now or datetime.now(UTC), "now"))
        with self._connection(immediate=True) as connection:
            lease = self._lease_from_row(self._require_row(connection, "operational_leases", "lease_id", selected_id))
            if lease.state != "active":
                raise LeaseUnavailable("lease is not active")
            if lease.owner != selected_owner:
                raise LeaseUnavailable("lease owner does not match")
            connection.execute(
                "UPDATE operational_leases SET state = 'released', released_at = ? WHERE lease_id = ?",
                (released_at, selected_id),
            )
            connection.execute(
                "UPDATE operational_work_items SET state = 'queued', updated_at = ? "
                "WHERE work_id = ? AND state IN ('leased', 'running')",
                (released_at, lease.work_id),
            )
            return self._lease_from_row(
                connection.execute("SELECT * FROM operational_leases WHERE lease_id = ?", (selected_id,)).fetchone()
            )

    def expire_leases(self, *, run_id: UUID | str | None = None, now: datetime) -> int:
        """Expire leases at or before ``now`` and expose their reconciliation state."""

        selected_now = _aware(now, "now")
        selected_run = None if run_id is None else _required_id(run_id, "run_id")
        stamp = _timestamp(selected_now)
        with self._connection(immediate=True) as connection:
            before = connection.execute(
                "SELECT COUNT(*) FROM operational_leases WHERE state = 'active' AND expires_at <= ? "
                + (
                    "AND work_id IN (SELECT work_id FROM operational_work_items WHERE run_id = ?)"
                    if selected_run
                    else ""
                ),
                (stamp,) if selected_run is None else (stamp, selected_run),
            ).fetchone()[0]
            self._expire_leases(connection, stamp, run_id=selected_run)
            return int(before)

    @contextmanager
    def _connection(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        if self.read_only and immediate:
            raise OperationalStoreError("read-only operational store rejects write transactions")
        connection: sqlite3.Connection | None = None
        try:
            if self.read_only:
                location = f"file:{quote(str(self.path), safe='/')}?mode=ro"
                connection = sqlite3.connect(location, timeout=30.0, uri=True)
            else:
                connection = sqlite3.connect(self.path, timeout=30.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 30000")
            if not self.read_only:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA synchronous = FULL")
            if immediate and not self.read_only:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if not self.read_only:
                connection.commit()
        except sqlite3.Error as error:
            if connection is not None and not self.read_only:
                connection.rollback()
            raise OperationalStoreError(f"operational database operation failed: {error}") from error
        except Exception:
            if connection is not None and not self.read_only:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    def _validate_existing_schema(self) -> None:
        try:
            with self._connection() as connection:
                row = connection.execute("SELECT schema_version FROM operational_schema WHERE singleton = 1").fetchone()
        except OperationalStoreError as error:
            raise OperationalStoreError("operational database does not contain the current schema") from error
        if row is None or int(row[0]) != SCHEMA_VERSION:
            raise OperationalStoreError(
                "operational database schema is stale; delete and recreate this disposable local database"
            )

    def _initialize_schema(self) -> None:
        with self._connection(immediate=True) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS operational_schema "
                "(singleton INTEGER PRIMARY KEY CHECK (singleton = 1), schema_version INTEGER NOT NULL, "
                "application_version TEXT NOT NULL, initialized_at TEXT NOT NULL)"
            )
            current = connection.execute("SELECT schema_version FROM operational_schema WHERE singleton = 1").fetchone()
            if current is not None and int(current[0]) != SCHEMA_VERSION:
                raise OperationalStoreError(
                    "operational database schema is stale; delete and recreate this disposable local database"
                )
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            if current is None:
                connection.execute(
                    "INSERT INTO operational_schema "
                    "(singleton,schema_version,application_version,initialized_at) VALUES (1,?,?,?)",
                    (SCHEMA_VERSION, self.application_version, _timestamp(datetime.now(UTC))),
                )

    @staticmethod
    def _expire_leases(connection: sqlite3.Connection, now_stamp: str, *, run_id: str | None = None) -> None:
        query = "SELECT lease_id, work_id FROM operational_leases WHERE state = 'active' AND expires_at <= ?"
        parameters: tuple[str, ...] = (now_stamp,)
        if run_id is not None:
            query += " AND work_id IN (SELECT work_id FROM operational_work_items WHERE run_id = ?)"
            parameters += (run_id,)
        expired = connection.execute(query, parameters).fetchall()
        if not expired:
            return
        for lease_id, work_id in expired:
            connection.execute(
                "UPDATE operational_leases SET state = 'expired', released_at = expires_at WHERE lease_id = ?",
                (lease_id,),
            )
            attempt_exists = (
                connection.execute(
                    "SELECT 1 FROM operational_attempts WHERE lease_id = ? LIMIT 1", (lease_id,)
                ).fetchone()
                is not None
            )
            connection.execute(
                "UPDATE operational_work_items SET state = ?, updated_at = ? "
                "WHERE work_id = ? AND state IN ('leased', 'running', 'cancel_requested')",
                ("unknown" if attempt_exists else "queued", now_stamp, work_id),
            )
            connection.execute(
                "UPDATE operational_planned_trials SET state = 'unknown', updated_at = ? "
                "WHERE trial_id = (SELECT trial_id FROM operational_work_items WHERE work_id = ?) "
                "AND state IN ('running', 'queued', 'planned') AND ? = 1",
                (now_stamp, work_id, int(attempt_exists)),
            )
            connection.execute(
                "UPDATE operational_attempts SET state = 'unknown', finished_at = ?, updated_at = ?, "
                "failure_kind = 'unknown_external_state', failure_class = 'unknown', "
                "failure_message = 'lease expired before reconciliation', reconciliation_state = 'pending' "
                "WHERE lease_id = ? AND state IN ('created', 'submitted', 'running')",
                (now_stamp, now_stamp, lease_id),
            )
            connection.execute(
                "UPDATE operational_backend_submissions SET state = 'unknown', updated_at = ?, "
                "reconciliation_state = 'pending' WHERE attempt_id IN "
                "(SELECT attempt_id FROM operational_attempts WHERE lease_id = ?)",
                (now_stamp, lease_id),
            )

    @staticmethod
    def _require_row(connection: sqlite3.Connection, table: str, column: str, value: str) -> sqlite3.Row:
        row = connection.execute(f"SELECT * FROM {table} WHERE {column} = ?", (value,)).fetchone()
        if row is None:
            raise OperationalStoreNotFound(f"{table} record not found: {value}")
        return cast(sqlite3.Row, row)

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            row[0],
            row[1],
            row[2],
            _parse_timestamp(row[3]),
            _optional_timestamp(row[4]),
            _optional_timestamp(row[5]),
            _parse_timestamp(row[6]),
            _optional_timestamp(row[7]),
        )

    @staticmethod
    def _plan_from_row(row: sqlite3.Row) -> PlanRecord:
        return PlanRecord(row[0], row[1], row[2], row[3], _parse_timestamp(row[4]), _parse_timestamp(row[5]))

    @staticmethod
    def _trial_from_row(row: sqlite3.Row) -> PlannedTrialRecord:
        return PlannedTrialRecord(
            row[0], row[1], row[2], row[3], row[4], _parse_timestamp(row[5]), _parse_timestamp(row[6])
        )

    @staticmethod
    def _work_item_from_row(row: sqlite3.Row) -> WorkItemRecord:
        return WorkItemRecord(
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            _parse_timestamp(row[7]),
            _parse_timestamp(row[8]),
            row[9],
            row[10],
            row[11],
            row[12],
            row[13],
            row[14],
            row[15],
            _parse_timestamp(row[16]),
            RetryPolicy.model_validate(json.loads(row[17])),
        )

    @staticmethod
    def _attempt_from_row(row: sqlite3.Row) -> AttemptRecord:
        return AttemptRecord(
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
            row[8],
            _parse_timestamp(row[9]),
            _optional_timestamp(row[10]),
            _optional_timestamp(row[11]),
            _parse_timestamp(row[12]),
            row[13],
            row[14],
            row[15],
            row[16],
            row[17],
        )

    @staticmethod
    def _submission_from_row(row: sqlite3.Row) -> BackendSubmissionRecord:
        return BackendSubmissionRecord(
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            _parse_timestamp(row[6]),
            _parse_timestamp(row[7]),
            row[8],
            row[9],
        )

    @staticmethod
    def _lease_from_row(row: sqlite3.Row) -> LeaseRecord:
        return LeaseRecord(
            row[0],
            row[1],
            row[2],
            _parse_timestamp(row[3]),
            _parse_timestamp(row[4]),
            _parse_timestamp(row[5]),
            row[6],
            _optional_timestamp(row[7]),
        )


def _required_id(value: UUID | str, label: str) -> str:
    try:
        return str(validate_uuidv7(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a UUIDv7") from error


def _required_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be blank")
    return value


def _required_key(value: str, label: str) -> str:
    try:
        return validate_entity_key(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a valid entity key") from error


def _required_ref(value: str, label: str) -> str:
    try:
        return str(PortableRelativePath(_required_text(value, label)))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a portable relative reference") from error


def _new_id(kind: EntityKind) -> str:
    return str(new_entity_id(kind))


def _installed_version() -> str:
    try:
        return version("aec-bench")
    except PackageNotFoundError:
        return "0.1.0"


def _checked_status(value: str, allowed: set[str]) -> str:
    if value not in allowed:
        raise ValueError(f"unsupported status: {value}")
    return value


def _checked_limits(limits: Mapping[str, int] | None) -> dict[str, int]:
    if limits is None:
        return {}
    checked: dict[str, int] = {}
    for key, value in limits.items():
        if not isinstance(key, str) or not key:
            raise ValueError("concurrency limit keys must not be blank")
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError("concurrency limits must be positive integers")
        checked[key] = value
    return checked


def _count_values(rows: list[sqlite3.Row], index: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row[index])
        counts[value] = counts.get(value, 0) + 1
    return counts


def _under_limit(value: str, limits: Mapping[str, int], counts: Mapping[str, int]) -> bool:
    limit = limits.get(value)
    return limit is None or counts.get(value, 0) < limit


def _work_item_priority_key(row: sqlite3.Row, now: datetime, starvation_after_seconds: int) -> tuple[object, ...]:
    created_at = _parse_timestamp(row[7])
    aged = now - created_at >= timedelta(seconds=starvation_after_seconds)
    if aged:
        return (0, created_at, int(row[10]), row[0])
    return (1, -int(row[6]), created_at, int(row[10]), row[0])


def _aware(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return value.astimezone(UTC)


def _timestamp(value: datetime) -> str:
    return _aware(value, "timestamp").isoformat()


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _optional_timestamp(value: str | None) -> datetime | None:
    return None if value is None else _parse_timestamp(value)


__all__ = (
    "AttemptRecord",
    "BackendSubmissionRecord",
    "LeaseRecord",
    "LeaseUnavailable",
    "OperationalStore",
    "OperationalStoreConflict",
    "OperationalStoreError",
    "OperationalStoreNotFound",
    "PlanRecord",
    "PlannedTrialRecord",
    "QueueCount",
    "RunRecord",
    "WorkItemRecord",
)
