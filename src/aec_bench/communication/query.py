# ABOUTME: Communication query helpers for safe report and export surfaces in aec-bench.
# ABOUTME: Enforces structural task-visibility filtering before public reporting consumes data.

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from aec_bench.contracts.task_definition import TaskDefinition, Visibility
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.api import query_ledger
from aec_bench.tasks.loader import load_task_catalog


def query_report_records(
    *,
    ledger_root: Path,
    tasks_root: Path,
    experiment_id: str | None = None,
    task_ids: Sequence[str] | None = None,
    task_prefix: str | None = None,
    adapter: str | None = None,
    model: str | None = None,
    include_holdout: bool = False,
) -> list[TrialRecord]:
    task_catalog = load_task_catalog(tasks_root)
    records = query_ledger(
        ledger_root,
        experiment_id=experiment_id,
        task_ids=task_ids,
        task_prefix=task_prefix,
        adapter=adapter,
        model=model,
    )
    if include_holdout:
        return [record for record in records if record.task.task_id in task_catalog]
    return [record for record in records if _is_public_record(record, task_catalog)]


def _is_public_record(record: TrialRecord, task_catalog: dict[str, TaskDefinition]) -> bool:
    task = task_catalog.get(record.task.task_id)
    if task is None:
        return False
    return task.visibility == Visibility.PUBLIC
