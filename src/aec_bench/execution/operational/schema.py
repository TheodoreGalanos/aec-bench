# ABOUTME: Defines the one current disposable SQLite schema for execution coordination.
# ABOUTME: Rejects stale local databases instead of retaining migration history or compatibility code.

SCHEMA_VERSION = 4

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS operational_runs (
        run_id TEXT PRIMARY KEY,
        status TEXT NOT NULL CHECK (status IN ('created', 'ready', 'running', 'completed', 'failed', 'cancelled')),
        spec_ref TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        updated_at TEXT NOT NULL,
        cancellation_requested_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operational_plans (
        plan_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES operational_runs(run_id),
        state TEXT NOT NULL CHECK (state IN ('draft', 'ready', 'started', 'closed')),
        plan_ref TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operational_planned_trials (
        trial_id TEXT PRIMARY KEY,
        plan_id TEXT NOT NULL REFERENCES operational_plans(plan_id),
        run_id TEXT NOT NULL REFERENCES operational_runs(run_id),
        ordinal INTEGER NOT NULL CHECK (ordinal > 0),
        state TEXT NOT NULL CHECK (
            state IN ('planned', 'queued', 'running', 'succeeded', 'failed', 'cancelled', 'invalid', 'unknown')
        ),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (plan_id, ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operational_work_items (
        work_id TEXT PRIMARY KEY,
        work_key TEXT NOT NULL,
        run_id TEXT NOT NULL REFERENCES operational_runs(run_id),
        trial_id TEXT NOT NULL UNIQUE REFERENCES operational_planned_trials(trial_id),
        kind TEXT NOT NULL,
        state TEXT NOT NULL CHECK (
            state IN (
                'planned', 'queued', 'leased', 'running', 'cancel_requested',
                'succeeded', 'failed', 'cancelled', 'invalid', 'unknown'
            )
        ),
        priority INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        plan_id TEXT NOT NULL REFERENCES operational_plans(plan_id),
        ordinal INTEGER NOT NULL CHECK (ordinal > 0),
        execution_family TEXT NOT NULL,
        backend TEXT NOT NULL,
        provider_route TEXT NOT NULL,
        model_route TEXT NOT NULL,
        resource_class TEXT NOT NULL,
        available_at TEXT NOT NULL,
        retry_policy_json TEXT NOT NULL,
        UNIQUE (run_id, work_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operational_leases (
        lease_id TEXT PRIMARY KEY,
        work_id TEXT NOT NULL REFERENCES operational_work_items(work_id),
        owner TEXT NOT NULL,
        acquired_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        heartbeat_at TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('active', 'expired', 'released')),
        released_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operational_attempts (
        attempt_id TEXT PRIMARY KEY,
        work_id TEXT NOT NULL REFERENCES operational_work_items(work_id),
        run_id TEXT NOT NULL REFERENCES operational_runs(run_id),
        trial_id TEXT NOT NULL REFERENCES operational_planned_trials(trial_id),
        attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
        candidate_index INTEGER NOT NULL CHECK (candidate_index > 0),
        retry_number INTEGER NOT NULL CHECK (retry_number >= 0),
        lease_id TEXT REFERENCES operational_leases(lease_id),
        state TEXT NOT NULL CHECK (
            state IN ('created', 'submitted', 'running', 'succeeded', 'failed', 'cancelled', 'unknown')
        ),
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        updated_at TEXT NOT NULL,
        failure_kind TEXT,
        failure_class TEXT,
        failure_message TEXT,
        reconciliation_state TEXT NOT NULL DEFAULT 'not_required',
        cancellation_status TEXT NOT NULL DEFAULT 'not_requested',
        UNIQUE (work_id, attempt_number),
        UNIQUE (work_id, candidate_index, retry_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operational_backend_submissions (
        submission_id TEXT PRIMARY KEY,
        attempt_id TEXT NOT NULL REFERENCES operational_attempts(attempt_id),
        backend TEXT NOT NULL,
        external_id TEXT,
        external_work_id TEXT,
        state TEXT NOT NULL CHECK (
            state IN ('submitted', 'accepted', 'running', 'completed', 'failed', 'cancelled', 'unknown')
        ),
        submitted_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        cancellation_status TEXT NOT NULL DEFAULT 'not_requested',
        reconciliation_state TEXT NOT NULL DEFAULT 'not_required',
        UNIQUE (attempt_id, backend)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS operational_active_lease_idx
        ON operational_leases (work_id) WHERE state = 'active'
    """,
    """
    CREATE INDEX IF NOT EXISTS operational_work_items_ready_idx
        ON operational_work_items (state, available_at, priority DESC, created_at, ordinal)
    """,
    """
    CREATE INDEX IF NOT EXISTS operational_attempts_trial_idx
        ON operational_attempts (trial_id, attempt_number)
    """,
    """
    CREATE INDEX IF NOT EXISTS operational_submissions_attempt_idx
        ON operational_backend_submissions (attempt_id, submitted_at)
    """,
)

__all__ = ("SCHEMA_STATEMENTS", "SCHEMA_VERSION")
