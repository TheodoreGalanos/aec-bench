# ABOUTME: Tests for append-only TrialRecord persistence in the Python ledger package.
# ABOUTME: Verifies deterministic paths, duplicate rejection, and round-trip reads.

from pathlib import Path

import pytest

from aec_bench.ledger.reader import _read_trial_record
from aec_bench.ledger.writer import DuplicateTrialRecordError, write_trial_record
from tests.support.trial_record_factories import make_trial_record


def test_write_trial_record_persists_json_and_supports_roundtrip(tmp_path: Path) -> None:
    record = make_trial_record()

    path = write_trial_record(ledger_root=tmp_path, record=record)

    assert path == tmp_path / "experiment-001" / "trial-001.json"
    assert _read_trial_record(path) == record


def test_write_trial_record_rejects_duplicate_trial_id(tmp_path: Path) -> None:
    record = make_trial_record()
    write_trial_record(ledger_root=tmp_path, record=record)

    with pytest.raises(DuplicateTrialRecordError, match="trial record already exists"):
        write_trial_record(ledger_root=tmp_path, record=record)
