# ABOUTME: Tests structural communication-query filtering over ledger-backed TrialRecords.
# ABOUTME: Verifies holdout records are excluded before reporting surfaces receive data.

from pathlib import Path

from aec_bench.communication.query import query_report_records
from aec_bench.contracts.task_definition import Visibility
from aec_bench.ledger.writer import write_trial_record
from tests.support.trial_record_factories import make_trial_record


def test_query_report_records_excludes_holdout_and_unknown_tasks_by_default(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/holdout-task",
        visibility=Visibility.HOLDOUT,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"}),
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-002",
            task={"task_id": "mechanical/heat-load/holdout-task", "task_revision": "git"},
        ),
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-003",
            task={"task_id": "mechanical/heat-load/missing-task", "task_revision": "git"},
        ),
    )

    records = query_report_records(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
    )

    assert [record.task.task_id for record in records] == ["mechanical/heat-load/public-task"]


def test_query_report_records_can_include_holdout_when_requested(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/holdout-task",
        visibility=Visibility.HOLDOUT,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"}),
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-002",
            task={"task_id": "mechanical/heat-load/holdout-task", "task_revision": "git"},
        ),
    )

    records = query_report_records(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        include_holdout=True,
    )

    assert {record.task.task_id for record in records} == {
        "mechanical/heat-load/holdout-task",
        "mechanical/heat-load/public-task",
    }


def _write_task_instance(*, tasks_root: Path, relative_path: str, visibility: Visibility) -> None:
    instance_dir = tasks_root / relative_path
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text(
        "Write findings to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text(
        f'[agent]\ntimeout_sec = 600\n\n[metadata]\nvisibility = "{visibility.value}"\n',
        encoding="utf-8",
    )
