# ABOUTME: Thin API layer over the append-only ledger for query and export operations.
# ABOUTME: Keeps scripts and future communication surfaces off raw filesystem traversal details.

from collections.abc import Sequence
from pathlib import Path

from aec_bench.contracts.jsonl import write_jsonl
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.reader import query_trial_records


def query_ledger(
    ledger_root: Path,
    *,
    experiment_id: str | None = None,
    dataset_id: str | None = None,
    task_ids: Sequence[str] | None = None,
    task_prefix: str | None = None,
    adapter: str | None = None,
    model: str | None = None,
) -> list[TrialRecord]:
    return query_trial_records(
        ledger_root,
        experiment_id=experiment_id,
        dataset_id=dataset_id,
        task_ids=task_ids,
        task_prefix=task_prefix,
        adapter=adapter,
        model=model,
    )


def export_trial_records_jsonl(
    ledger_root: Path,
    *,
    output_path: Path,
    experiment_id: str | None = None,
    task_ids: Sequence[str] | None = None,
    task_prefix: str | None = None,
    adapter: str | None = None,
    model: str | None = None,
) -> Path:
    records = query_ledger(
        ledger_root,
        experiment_id=experiment_id,
        task_ids=task_ids,
        task_prefix=task_prefix,
        adapter=adapter,
        model=model,
    )
    write_jsonl(output_path, records)
    return output_path
