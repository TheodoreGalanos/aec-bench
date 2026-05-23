# ABOUTME: Append-only TrialRecord persistence helpers for the Python ledger package.
# ABOUTME: Writes one JSON record per trial and rejects duplicate trial IDs within an experiment.

from pathlib import Path

from aec_bench.contracts.trial_record import TrialRecord


class DuplicateTrialRecordError(Exception):
    pass


def write_trial_record(*, ledger_root: Path, record: TrialRecord) -> Path:
    path = ledger_root / record.experiment_id / f"{record.trial_id}.json"
    if path.exists():
        raise DuplicateTrialRecordError(f"trial record already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path


def write_trial_records(*, ledger_root: Path, records: list[TrialRecord]) -> list[Path]:
    return [write_trial_record(ledger_root=ledger_root, record=record) for record in records]
