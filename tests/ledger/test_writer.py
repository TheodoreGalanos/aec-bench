# ABOUTME: Tests for append-only TrialRecord persistence in the Python ledger package.
# ABOUTME: Verifies deterministic paths, duplicate rejection, and round-trip reads.

from pathlib import Path

import pytest

import aec_bench.ledger.durability as durability
from aec_bench.ledger.durability import mkdir_durable
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


def test_mkdir_durable_fsyncs_each_new_parent_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flushed: list[Path] = []
    monkeypatch.setattr(durability, "fsync_directory", flushed.append)
    target = tmp_path / "ledger" / "experiment" / "_artifacts"

    mkdir_durable(target)

    assert target.is_dir()
    assert flushed == [tmp_path, tmp_path / "ledger", tmp_path / "ledger" / "experiment"]
