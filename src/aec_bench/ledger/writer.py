# ABOUTME: Append-only TrialRecord persistence helpers for the Python ledger package.
# ABOUTME: Writes one JSON record per trial and rejects duplicate trial IDs within an experiment.

import os
import uuid
from pathlib import Path

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.durability import fsync_directory, mkdir_durable


class DuplicateTrialRecordError(Exception):
    pass


def write_trial_record(*, ledger_root: Path, record: TrialRecord) -> Path:
    path = ledger_root / record.experiment_id / f"{record.trial_id}.json"
    mkdir_durable(path.parent)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        _write_record_temp(temporary, record.model_dump_json(indent=2))
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise DuplicateTrialRecordError(f"trial record already exists: {path}") from exc
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def write_trial_records(*, ledger_root: Path, records: list[TrialRecord]) -> list[Path]:
    return [write_trial_record(ledger_root=ledger_root, record=record) for record in records]


def _write_record_temp(path: Path, payload: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
