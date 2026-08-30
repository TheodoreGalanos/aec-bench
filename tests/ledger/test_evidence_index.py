# ABOUTME: Tests disposable evidence indexing and metadata-only cursor queries.
# ABOUTME: Proves rebuilds preserve portable records and reject stale or conflicting index input.

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aec_bench.contracts.execution_release import WorldExecutionRelease
from aec_bench.contracts.experiment_manifest import ComputeConfig
from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.contracts.task_snapshot import RepositoryTaskSnapshotRef
from aec_bench.contracts.trial_record import PlannedTrialBinding
from aec_bench.ledger.index import EvidenceIndex, EvidenceIndexSchemaError
from aec_bench.ledger.query import EvidenceQuery, EvidenceQueryError
from aec_bench.ledger.writer import write_trial_record, write_trial_record_at
from tests.support.trial_record_factories import make_trial_record


def test_rebuild_indexes_metadata_and_paginates_with_a_bound_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_a = make_trial_record(trial_id="trial-a", timestamp=datetime(2026, 3, 13, 10, 0, tzinfo=UTC))
    record_b = make_trial_record(trial_id="trial-b", timestamp=datetime(2026, 3, 13, 10, 0, tzinfo=UTC))
    record_c = make_trial_record(
        trial_id="trial-c",
        timestamp=datetime(2026, 3, 13, 11, 0, tzinfo=UTC),
        execution_status="failed",
        evaluation_status="not_requested",
        evaluation=None,
    )
    for record in (record_b, record_c, record_a):
        write_trial_record(ledger_root=tmp_path / "ledger", record=record)

    index = EvidenceIndex(tmp_path / "index.sqlite")
    before = (tmp_path / "ledger" / "experiment-001" / "trial-a.json").read_bytes()
    report = index.rebuild(tmp_path / "ledger")
    assert report.indexed == 3
    assert report.unreadable == 0
    assert report.conflicts == 0
    assert (tmp_path / "ledger" / "experiment-001" / "trial-a.json").read_bytes() == before

    query = EvidenceQuery(index)
    first = query.page(page_size=2, model="anthropic:claude-sonnet-4-20250514")
    assert [row.trial_id for row in first.rows] == ["trial-a", "trial-b"]
    assert first.next_cursor is not None
    second = query.page(page_size=2, model="anthropic:claude-sonnet-4-20250514", after_cursor=first.next_cursor)
    assert [row.trial_id for row in second.rows] == ["trial-c"]
    assert second.rows[0].execution_status == "failed"
    assert second.rows[0].task_revision == "git-sha-task"
    assert second.rows[0].attempt == 1
    assert first.rows[0].reward == 1.0

    monkeypatch.setattr("aec_bench.ledger.reader.read_trial_record", lambda *_args, **_kwargs: pytest.fail("hydrated"))
    assert [row.trial_id for row in query.page().rows] == ["trial-a", "trial-b", "trial-c"]


def test_query_filters_provider_evidence_and_rejects_cursor_filter_changes(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    write_trial_record(ledger_root=ledger, record=make_trial_record())
    index = EvidenceIndex(tmp_path / "index.sqlite")
    index.rebuild(ledger)
    query = EvidenceQuery(index)

    page = query.page(provider_evidence_missing=True)
    assert len(page.rows) == 1
    assert page.rows[0].provider_evidence_present is False
    page = query.page(page_size=1)
    assert page.next_cursor is None


def test_rebuild_indexes_world_profile_identity(tmp_path: Path) -> None:
    run_id = new_entity_id(EntityKind.RUN)
    trial_id = new_entity_id(EntityKind.TRIAL)
    task_identity = EntityIdentity(id=new_entity_id(EntityKind.TASK), key="world/task", version=1)
    task_release = RepositoryTaskSnapshotRef(
        task_id="world/task",
        task_identity=task_identity,
        source_revision="a" * 40,
        task_path="tasks/world",
    )
    world_release = WorldExecutionRelease(
        world_identity=EntityIdentity(id=new_entity_id(EntityKind.WORLD), key="world", version=1),
        profile_identity=EntityIdentity(id=new_entity_id(EntityKind.WORLD_PROFILE), key="world/profile", version=1),
        world_build=WorldBuildRef(task_world_id="world", entry_point="main", artifact_sha256="b" * 64),
        profile=InteractiveWorldProfileRef(
            task_world_id="world",
            profile_id="profile",
            profile_content_sha256="c" * 64,
        ),
    )
    record = make_trial_record(
        trial_id=str(trial_id),
        run_id=str(run_id),
        task={"task_id": "world/task", "task_revision": "git-sha-task"},
        input={
            "instruction": "Run the world.",
            "task_revision": "git-sha-task",
            "task_kind": "world",
        },
    )
    record.planned_trial_binding = PlannedTrialBinding(
        run_identity=EntityIdentity(id=run_id, key="run", version=1),
        trial_identity=EntityIdentity(id=trial_id, key="trial", version=1),
        task_release=task_release,
        agent_condition_identity=EntityIdentity(
            id=new_entity_id(EntityKind.AGENT_CONDITION),
            key="agent/condition",
            version=1,
        ),
        ordinal=1,
        repetition=1,
        compute=ComputeConfig(backend="modal"),
        family_release=world_release,
        execution_family="world",
    )
    record.bind_run_manifest(record.run_manifest)
    write_trial_record(ledger_root=tmp_path / "ledger", record=record)

    index = EvidenceIndex(tmp_path / "index.sqlite")
    index.rebuild(tmp_path / "ledger")

    rows = EvidenceQuery(index).page(world_profile_id="profile").rows
    assert [row.trial_id for row in rows] == [str(trial_id)]


def test_rebuild_reports_unreadable_and_conflicting_records(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    record = make_trial_record()
    write_trial_record(ledger_root=ledger, record=record)
    invalid = ledger / "experiment-001" / "unreadable.json"
    invalid.write_text("not json", encoding="utf-8")
    conflict = ledger / "portable-run" / "trial-records" / "trial-001.json"
    write_trial_record_at(path=conflict, record=record)
    third_conflict = ledger / "portable-run-2" / "trial-records" / "trial-001.json"
    write_trial_record_at(path=third_conflict, record=record)
    (ledger / "portable-run" / "resolved-run-spec.json").write_text("run metadata", encoding="utf-8")

    index = EvidenceIndex(tmp_path / "index.sqlite")
    report = index.rebuild(ledger)

    assert report.indexed == 0
    assert report.unreadable == 1
    assert report.conflicts == 2
    assert any("unreadable.json" in error for error in report.errors)
    assert any("duplicate trial_id" in error for error in report.errors)


def test_rebuild_ignores_non_trial_json_in_portable_run_directories(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    run_directory = ledger / "portable-run"
    record = make_trial_record()
    write_trial_record_at(path=run_directory / "trial-records" / "trial-001.json", record=record)
    for directory in ("receipts", "finalizations", "harbor-mappings"):
        path = run_directory / directory / "metadata.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"not": "a TrialRecord"}', encoding="utf-8")
    (run_directory / "resolved-run-spec.json").write_text('{"not": "a TrialRecord"}', encoding="utf-8")

    report = EvidenceIndex(tmp_path / "index.sqlite").rebuild(ledger)

    assert report.indexed == 1
    assert report.unreadable == 0
    assert report.conflicts == 0


def test_stale_index_schema_requires_recreation(tmp_path: Path) -> None:
    database = tmp_path / "index.sqlite"
    EvidenceIndex(database)
    connection = sqlite3.connect(database)
    tables = {
        str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert tables == {"evidence_index_metadata", "evidence_trial_records"}
    connection.execute("UPDATE evidence_index_metadata SET schema_version = 999")
    connection.commit()
    connection.close()

    with pytest.raises(EvidenceIndexSchemaError, match="recreate"):
        EvidenceIndex(database)


def test_rebuild_rejects_symlinked_record_path(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    source = tmp_path / "outside.json"
    source.write_text(make_trial_record().model_dump_json(), encoding="utf-8")
    linked = ledger / "experiment-001" / "trial-001.json"
    linked.parent.mkdir(parents=True)
    linked.symlink_to(source)

    report = EvidenceIndex(tmp_path / "index.sqlite").rebuild(ledger)

    assert report.indexed == 0
    assert report.unreadable == 1
    assert "symlink" in report.errors[0]


def test_cursor_is_bound_to_generation_and_query_filters(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    write_trial_record(ledger_root=ledger, record=make_trial_record())
    write_trial_record(ledger_root=ledger, record=make_trial_record(trial_id="trial-002"))
    index = EvidenceIndex(tmp_path / "index.sqlite")
    index.rebuild(ledger)
    query = EvidenceQuery(index)
    page = query.page(page_size=1, task_prefix="electrical/")
    assert page.next_cursor is not None
    with pytest.raises(EvidenceQueryError, match="does not match"):
        query.page(page_size=1, task_prefix="mechanical/", after_cursor=page.next_cursor)

    with pytest.raises(EvidenceQueryError, match="page_size"):
        query.page(page_size=1001)

    index.rebuild(ledger)
    with pytest.raises(EvidenceQueryError, match="stale"):
        query.page(page_size=1, task_prefix="electrical/", after_cursor=page.next_cursor)
