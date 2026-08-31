# ABOUTME: Tests for ledger read and query helpers in the Python ledger package.
# ABOUTME: Verifies deterministic trial discovery, round-trip loading, and common filters.

from pathlib import Path

from aec_bench.ledger.reader import (
    _iter_trial_record_paths,
    query_trial_records,
    read_trial_records,
)
from aec_bench.ledger.writer import write_trial_record
from tests.support.trial_record_factories import make_trial_record


def test_iter_trial_record_paths_returns_sorted_json_files(tmp_path: Path) -> None:
    record_b = make_trial_record(trial_id="trial-002")
    record_a = make_trial_record(trial_id="trial-001")
    write_trial_record(ledger_root=tmp_path, record=record_b)
    write_trial_record(ledger_root=tmp_path, record=record_a)

    paths = _iter_trial_record_paths(tmp_path)

    assert [path.name for path in paths] == ["trial-001.json", "trial-002.json"]


def test_read_trial_records_loads_written_records(tmp_path: Path) -> None:
    record_a = make_trial_record(trial_id="trial-001")
    record_b = make_trial_record(trial_id="trial-002")
    write_trial_record(ledger_root=tmp_path, record=record_a)
    write_trial_record(ledger_root=tmp_path, record=record_b)

    records = read_trial_records(tmp_path)

    assert [record.trial_id for record in records] == ["trial-001", "trial-002"]


def test_query_trial_records_filters_by_experiment_task_and_adapter(tmp_path: Path) -> None:
    keep = make_trial_record()
    other_experiment = make_trial_record(trial_id="trial-002", experiment_id="experiment-002")
    other_task = make_trial_record(
        trial_id="trial-003",
        task={"task_id": "mechanical/heat-load/demo-instance", "task_revision": "git-sha-task"},
    )
    other_adapter = make_trial_record(
        trial_id="trial-004",
        agent={
            "adapter": "direct-anthropic",
            "model": "anthropic:claude-sonnet-4-20250514",
            "adapter_revision": "git-sha-adapter",
            "configuration": {"temperature": 0.0},
        },
    )
    for record in [keep, other_experiment, other_task, other_adapter]:
        write_trial_record(ledger_root=tmp_path, record=record)

    records = query_trial_records(
        tmp_path,
        experiment_id="experiment-001",
        task_prefix="electrical/",
        adapter="tool_loop",
    )

    assert [record.trial_id for record in records] == ["trial-001"]


def test_query_trial_records_filters_by_exact_task_ids(tmp_path: Path) -> None:
    keep = make_trial_record(
        task={"task_id": "mechanical/heat-load/alpha", "task_revision": "git-sha-task"},
    )
    other = make_trial_record(
        trial_id="trial-002",
        task={"task_id": "mechanical/heat-load/beta", "task_revision": "git-sha-task"},
    )
    for record in [keep, other]:
        write_trial_record(ledger_root=tmp_path, record=record)

    records = query_trial_records(
        tmp_path,
        task_ids=["mechanical/heat-load/alpha"],
    )

    assert [record.trial_id for record in records] == ["trial-001"]


def test_query_trial_records_filters_by_model(tmp_path: Path) -> None:
    keep = make_trial_record()
    other = make_trial_record(
        trial_id="trial-002",
        agent={
            "adapter": "tool_loop",
            "model": "openai:gpt-4.1-mini",
            "adapter_revision": "git-sha-adapter",
            "configuration": {},
        },
    )
    for record in [keep, other]:
        write_trial_record(ledger_root=tmp_path, record=record)

    records = query_trial_records(
        tmp_path,
        model="anthropic:claude-sonnet-4-20250514",
    )

    assert [record.trial_id for record in records] == ["trial-001"]


def test_iter_trial_record_paths_returns_empty_for_nonexistent_root(tmp_path: Path) -> None:
    paths = _iter_trial_record_paths(tmp_path / "does-not-exist")

    assert paths == []


def test_read_trial_records_returns_empty_for_empty_ledger(tmp_path: Path) -> None:
    records = read_trial_records(tmp_path)

    assert records == []


def test_iter_trial_record_paths_scopes_to_experiment(tmp_path: Path) -> None:
    record_a = make_trial_record(trial_id="trial-001", experiment_id="exp-a")
    record_b = make_trial_record(trial_id="trial-002", experiment_id="exp-b")
    write_trial_record(ledger_root=tmp_path, record=record_a)
    write_trial_record(ledger_root=tmp_path, record=record_b)

    paths = _iter_trial_record_paths(tmp_path, experiment_id="exp-a")

    assert len(paths) == 1
    assert paths[0].name == "trial-001.json"


def test_reader_skips_underscore_prefixed_directories(tmp_path: Path) -> None:
    """Trial record paths should not include files from _-prefixed directories."""
    record = make_trial_record(experiment_id="exp-001")
    write_trial_record(ledger_root=tmp_path, record=record)

    # Write a fake evaluation artifact in _evaluations/
    eval_dir = tmp_path / "exp-001" / "_evaluations"
    eval_dir.mkdir()
    (eval_dir / "eval-001.json").write_text('{"not": "a trial"}')

    paths = _iter_trial_record_paths(tmp_path, experiment_id="exp-001")
    assert len(paths) == 1
    assert paths[0].name == "trial-001.json"


def test_read_trial_records_reads_current_files_on_each_call(tmp_path: Path) -> None:
    """Repeated reads reflect the current portable ledger files."""
    record = make_trial_record(trial_id="trial-001")
    write_trial_record(ledger_root=tmp_path, record=record)

    first = read_trial_records(tmp_path)
    assert [r.trial_id for r in first] == ["trial-001"]

    second = read_trial_records(tmp_path)

    assert [r.trial_id for r in second] == ["trial-001"]
    assert first is not second


def test_read_trial_records_sees_new_trial_written_after_read(tmp_path: Path) -> None:
    """A new trial written after a read is visible on the next read."""
    record_a = make_trial_record(trial_id="trial-001")
    write_trial_record(ledger_root=tmp_path, record=record_a)

    first = read_trial_records(tmp_path)
    assert [r.trial_id for r in first] == ["trial-001"]

    record_b = make_trial_record(trial_id="trial-002")
    write_trial_record(ledger_root=tmp_path, record=record_b)
    second = read_trial_records(tmp_path)

    assert [r.trial_id for r in second] == ["trial-001", "trial-002"]
    assert first is not second


def test_read_trial_records_scoped_and_unscoped_reads_are_independent(tmp_path: Path) -> None:
    """Scoped and unscoped reads use their explicit path selections."""
    record_a = make_trial_record(trial_id="trial-001", experiment_id="exp-a")
    record_b = make_trial_record(trial_id="trial-002", experiment_id="exp-b")
    write_trial_record(ledger_root=tmp_path, record=record_a)
    write_trial_record(ledger_root=tmp_path, record=record_b)

    scoped = read_trial_records(tmp_path, experiment_id="exp-a")
    unscoped = read_trial_records(tmp_path)

    assert [r.trial_id for r in scoped] == ["trial-001"]
    assert [r.trial_id for r in unscoped] == ["trial-001", "trial-002"]
    assert scoped is not unscoped
