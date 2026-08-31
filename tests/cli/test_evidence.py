# ABOUTME: Exercises the public evidence index rebuild and verification commands.
# ABOUTME: Proves structured results, partial failures, run scoping, and byte checks without providers.

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id
from aec_bench.execution.models import (
    AttemptProcessStatus,
    AttemptReceipt,
    AttemptResourceUsage,
    CancellationStatus,
    FinalizationState,
    ReconciliationState,
    TrialFinalization,
)
from aec_bench.ledger.evidence_run_store import EvidenceRunState, EvidenceRunStore
from aec_bench.ledger.index import EvidenceIndex
from aec_bench.ledger.verification import verify_evidence
from aec_bench.ledger.writer import write_append_only_json_at, write_trial_record, write_trial_record_at
from tests.contracts.test_run_plan import _resolved_run
from tests.support.trial_record_factories import make_trial_record

runner = CliRunner()


def _data(result: object) -> dict[str, object]:
    return json.loads(result.stdout)["data"]  # type: ignore[union-attr]


def test_evidence_index_rebuild_command_returns_structured_report(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    write_trial_record(ledger_root=ledger, record=make_trial_record())
    database = tmp_path / "index.sqlite"
    before = {path.relative_to(ledger): path.read_bytes() for path in ledger.rglob("*") if path.is_file()}

    result = runner.invoke(
        app,
        ["--json", "evidence", "index", "rebuild", "--ledger-root", str(ledger), "--database", str(database)],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["command"] == "evidence index rebuild"
    assert _data(result)["indexed"] == 1
    assert database.is_file()
    assert {path.relative_to(ledger): path.read_bytes() for path in ledger.rglob("*") if path.is_file()} == before


def test_evidence_index_rebuild_command_reports_unreadable_records(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    write_trial_record(ledger_root=ledger, record=make_trial_record())
    (ledger / "experiment-001" / "broken.json").write_text("not json", encoding="utf-8")

    result = runner.invoke(app, ["--json", "evidence", "index", "rebuild", "--ledger-root", str(ledger)])

    assert result.exit_code == 2
    envelope = json.loads(result.stdout)
    assert envelope["status"] == "partial"
    assert _data(result)["unreadable"] == 1
    assert envelope["errors"]


def test_evidence_index_rebuild_replaces_a_stale_database(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    write_trial_record(ledger_root=ledger, record=make_trial_record())
    database = tmp_path / "index.sqlite"
    EvidenceIndex(database)
    connection = sqlite3.connect(database)
    connection.execute("UPDATE evidence_index_metadata SET schema_version = 999")
    connection.commit()
    connection.close()
    database.with_name(database.name + "-wal").write_bytes(b"stale wal")
    database.with_name(database.name + "-shm").write_bytes(b"stale shm")

    result = runner.invoke(
        app,
        ["--json", "evidence", "index", "rebuild", "--ledger-root", str(ledger), "--database", str(database)],
    )

    assert result.exit_code == 0, result.stdout
    assert _data(result)["indexed"] == 1
    assert not database.with_name(database.name + "-wal").exists()
    assert not database.with_name(database.name + "-shm").exists()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT schema_version FROM evidence_index_metadata").fetchone() == (1,)
    second = runner.invoke(
        app,
        ["--json", "evidence", "index", "rebuild", "--ledger-root", str(ledger), "--database", str(database)],
    )
    assert second.exit_code == 0, second.stdout
    assert _data(second)["generation"] == _data(result)["generation"] + 1


def test_evidence_index_rebuild_preserves_target_on_fatal_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ledger = tmp_path / "ledger"
    database = tmp_path / "index.sqlite"
    EvidenceIndex(database).rebuild(ledger)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE evidence_index_metadata SET schema_version = 999")
        connection.commit()
    original_bytes = database.read_bytes()

    def fail_rebuild(self: object, ledger_root: Path) -> object:
        raise RuntimeError(f"cannot scan {ledger_root}")

    monkeypatch.setattr(EvidenceIndex, "rebuild", fail_rebuild)
    result = runner.invoke(
        app,
        ["--json", "evidence", "index", "rebuild", "--ledger-root", str(ledger), "--database", str(database)],
    )

    assert result.exit_code == 1
    assert database.read_bytes() == original_bytes
    assert not list(database.parent.glob(f".{database.name}.*.tmp"))


def test_evidence_verify_command_scopes_before_reporting_unrelated_corruption(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    write_trial_record(ledger_root=ledger, record=make_trial_record(run_id="run-a"))
    write_trial_record(ledger_root=ledger, record=make_trial_record(trial_id="trial-b", run_id="run-b"))
    (ledger / "experiment-001" / "unrelated-broken.json").write_text("not json", encoding="utf-8")

    result = runner.invoke(app, ["--json", "evidence", "verify", "--run", "run-a", "--ledger-root", str(ledger)])

    assert result.exit_code == 0, result.stdout
    assert _data(result)["records"] == 1
    assert _data(result)["errors"] == []


def test_evidence_verify_command_rejects_an_unknown_run_selector(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["--json", "evidence", "verify", "--run", "missing-run", "--ledger-root", str(tmp_path / "ledger")],
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout)["status"] == "error"


def test_evidence_verify_command_reports_corrupted_referenced_bytes(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    source = tmp_path / "output.json"
    source.write_text("original", encoding="utf-8")
    record = make_trial_record()
    record.attach_artifact("raw_output", source, media_type="application/json")
    write_trial_record(ledger_root=ledger, record=record)
    reference = record.output.artifacts[-1].artifact  # type: ignore[union-attr]
    (ledger / "_artifacts" / reference.artifact_id).write_text("corrupted", encoding="utf-8")

    result = runner.invoke(app, ["--json", "evidence", "verify", "--ledger-root", str(ledger)])

    assert result.exit_code == 2
    envelope = json.loads(result.stdout)
    assert envelope["status"] == "partial"
    assert _data(result)["records"] == 0
    assert any("mismatch" in error or "integrity" in error for error in envelope["errors"])


def test_evidence_verify_discovers_run_with_corrupt_or_missing_trial_records(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    run_identity = EntityIdentity(id=new_entity_id(EntityKind.RUN), key="run-a", version=1)
    run_dir = ledger / "run-a" / "trial-records"
    run_dir.mkdir(parents=True)
    (run_dir / "broken.json").write_text("not json", encoding="utf-8")
    (run_dir.parent / "state.json").write_text(
        EvidenceRunState(state="draft", run_identity=run_identity).model_dump_json(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["--json", "evidence", "verify", "--run", str(run_identity.id), "--ledger-root", str(ledger)],
    )

    assert result.exit_code == 2
    assert _data(result)["records"] == 0
    assert any("broken.json" in error for error in json.loads(result.stdout)["errors"])


def test_evidence_verify_allows_valid_draft_run_without_a_plan(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(ledger)
    store.create_run(spec)

    report = verify_evidence(ledger, run_id=str(spec.run_identity.id))

    assert report.errors == ()
    assert report.records == 0


def test_evidence_verify_rejects_portable_record_from_another_run(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    expected = _resolved_run(repetitions=1)
    store = EvidenceRunStore(ledger)
    store.create_run(expected)
    record = make_trial_record(run_id="different-run")
    write_trial_record_at(
        path=store.run_directory(expected.run_identity) / "trial-records" / "trial.json",
        record=record,
    )

    report = verify_evidence(ledger)

    assert any("run_id does not match" in error for error in report.errors)
    assert report.records == 0


def test_evidence_verify_rejects_finalization_reference_outside_run_trial_records(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    trial_id = new_entity_id(EntityKind.TRIAL)
    attempt_id = new_entity_id(EntityKind.ATTEMPT)
    record = make_trial_record(trial_id=str(trial_id), run_id="run-a")
    trial_records = ledger / "run-a" / "trial-records"
    write_trial_record_at(path=trial_records / "trial.json", record=record)
    write_trial_record(ledger_root=ledger, record=record)
    finalization = TrialFinalization(
        finalization_id=new_entity_id(EntityKind.RECEIPT),
        trial_id=trial_id,
        attempt_id=attempt_id,
        record_version=1,
        trial_record_ref=f"experiment-001/{trial_id}.json",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        state=FinalizationState.CURRENT,
    )
    write_append_only_json_at(
        path=trial_records.parent / "finalizations" / "finalization.json",
        payload=finalization.model_dump_json(),
    )

    report = verify_evidence(ledger)

    assert report.finalizations == 0
    assert any("trial-records directory" in error for error in report.errors)


def test_evidence_verify_counts_valid_portable_receipt_and_finalization(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger"
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(ledger)
    store.create_run(spec)
    run_dir = store.run_directory(spec.run_identity)
    source = tmp_path / "output.json"
    source.write_text("portable output", encoding="utf-8")
    trial_id = new_entity_id(EntityKind.TRIAL)
    attempt_id = new_entity_id(EntityKind.ATTEMPT)
    record = make_trial_record(trial_id=str(trial_id), run_id=str(spec.run_identity.id))
    record.attach_artifact("raw_output", source, media_type="application/json")
    record_path = run_dir / "trial-records" / f"{trial_id}.json"
    write_trial_record_at(path=record_path, record=record)
    output_reference = record.output.artifacts[-1].artifact  # type: ignore[union-attr]
    receipt = AttemptReceipt(
        receipt_id=new_entity_id(EntityKind.RECEIPT),
        receipt_key="trial-attempt-receipt",
        attempt_id=attempt_id,
        backend="local",
        submission_id=new_entity_id(EntityKind.BACKEND_SUBMISSION),
        requested_condition=spec.agent_conditions[0].identity,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
        process_status=AttemptProcessStatus.SUCCEEDED,
        cancellation_status=CancellationStatus.NOT_REQUESTED,
        resource_usage=AttemptResourceUsage(wall_seconds=1.0),
        output_references=(output_reference,),
        reconciliation_status=ReconciliationState.NOT_REQUIRED,
    )
    write_append_only_json_at(
        path=run_dir / "receipts" / "receipt.json",
        payload=receipt.model_dump_json(),
    )
    finalization = TrialFinalization(
        finalization_id=new_entity_id(EntityKind.RECEIPT),
        trial_id=trial_id,
        attempt_id=attempt_id,
        record_version=1,
        trial_record_ref=str(record_path.relative_to(ledger)),
        published_at=datetime(2026, 1, 1, 0, 0, 2, tzinfo=UTC),
        state=FinalizationState.CURRENT,
    )
    write_append_only_json_at(
        path=run_dir / "finalizations" / "finalization.json",
        payload=finalization.model_dump_json(),
    )

    report = verify_evidence(ledger, run_id=str(spec.run_identity.id))

    assert report.errors == ()
    assert report.records == 1
    assert report.receipts == 1
    assert report.finalizations == 1
    assert report.artifacts == 2
