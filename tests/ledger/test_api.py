# ABOUTME: Tests for the higher-level ledger API used by scripts and future communication surfaces.
# ABOUTME: Verifies filtered query, JSONL export, and type-safe return values.

from pathlib import Path

from aec_bench.contracts.jsonl import read_jsonl
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.api import export_trial_records_jsonl, query_ledger
from aec_bench.ledger.writer import write_trial_record
from tests.support.trial_record_factories import make_trial_record


def test_query_ledger_filters_records_and_export_writes_jsonl(tmp_path: Path) -> None:
    write_trial_record(ledger_root=tmp_path, record=make_trial_record())
    write_trial_record(
        ledger_root=tmp_path,
        record=make_trial_record(
            trial_id="trial-002",
            experiment_id="experiment-002",
        ),
    )

    records = query_ledger(tmp_path, experiment_id="experiment-001")
    output_path = export_trial_records_jsonl(
        tmp_path,
        output_path=tmp_path / "export.jsonl",
        experiment_id="experiment-001",
    )

    assert len(records) == 1
    assert output_path.name == "export.jsonl"
    assert len(read_jsonl(output_path)) == 1


def test_query_ledger_returns_trial_records(tmp_path: Path) -> None:
    write_trial_record(ledger_root=tmp_path, record=make_trial_record())

    records = query_ledger(tmp_path)

    assert len(records) == 1
    assert isinstance(records[0], TrialRecord)


def test_query_ledger_returns_empty_for_nonexistent_root(tmp_path: Path) -> None:
    records = query_ledger(tmp_path / "does-not-exist")

    assert records == []


def test_query_ledger_returns_empty_for_missing_experiment(tmp_path: Path) -> None:
    write_trial_record(ledger_root=tmp_path, record=make_trial_record())

    records = query_ledger(tmp_path, experiment_id="no-such-experiment")

    assert records == []
