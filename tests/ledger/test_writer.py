# ABOUTME: Tests for append-only TrialRecord persistence in the Python ledger package.
# ABOUTME: Verifies deterministic paths, duplicate rejection, and round-trip reads.

import json
import stat
from pathlib import Path

import pytest

import aec_bench.ledger.durability as durability
from aec_bench.ledger.durability import mkdir_durable
from aec_bench.ledger.reader import read_trial_record
from aec_bench.ledger.writer import DuplicateTrialRecordError, run_manifest_path, write_trial_record
from tests.support.trial_record_factories import make_trial_record


def test_write_trial_record_persists_json_and_supports_roundtrip(tmp_path: Path) -> None:
    record = make_trial_record()

    path = write_trial_record(ledger_root=tmp_path, record=record)

    assert path == tmp_path / "experiment-001" / "trial-001.json"
    loaded = read_trial_record(path, ledger_root=tmp_path)
    assert loaded.model_dump(mode="json") == record.model_dump(mode="json")
    assert loaded.run_manifest == record.run_manifest
    assert run_manifest_path(
        ledger_root=tmp_path,
        experiment_id=record.experiment_id,
        run_id=record.run_id,
    ).is_file()


def test_write_trial_record_retains_logical_artifact_role_without_host_path(tmp_path: Path) -> None:
    symbolic_state = tmp_path / "workspace" / "symbolic_state.json"
    symbolic_state.parent.mkdir()
    symbolic_state.write_text('{"pressure": 42}', encoding="utf-8")
    record = make_trial_record()
    record.attach_artifact(
        "symbolic_state",
        symbolic_state,
        media_type="application/json",
        logical_path="symbolic_state.json",
    )

    path = write_trial_record(ledger_root=tmp_path / "ledger", record=record)
    loaded = read_trial_record(path, ledger_root=tmp_path / "ledger")

    assert loaded.output is not None
    retained_path = loaded.output.artifact_path("symbolic_state")
    assert retained_path is not None
    assert Path(retained_path).read_text(encoding="utf-8") == '{"pressure": 42}'
    persisted = path.read_text(encoding="utf-8")
    assert str(symbolic_state) not in persisted
    assert '"logical_path":"symbolic_state.json"' in persisted.replace(" ", "").replace("\n", "")


def test_write_trial_record_rejects_duplicate_trial_id(tmp_path: Path) -> None:
    record = make_trial_record()
    write_trial_record(ledger_root=tmp_path, record=record)

    with pytest.raises(DuplicateTrialRecordError, match="trial record already exists"):
        write_trial_record(ledger_root=tmp_path, record=record)


def test_write_trial_record_supports_valid_long_public_file_name(tmp_path: Path) -> None:
    trial_id = "t" * 230
    record = make_trial_record(trial_id=trial_id)

    path = write_trial_record(ledger_root=tmp_path, record=record)

    assert path.name == f"{trial_id}.json"
    assert len(path.name.encode()) < 256
    assert read_trial_record(path, ledger_root=tmp_path).trial_id == trial_id


def test_read_trial_record_rejects_unknown_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "experiment" / "trial.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"schema_version": 3}), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported TrialRecord schema_version: 3"):
        read_trial_record(path)


def test_read_trial_record_rejects_missing_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "experiment" / "trial.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"trial_id": "old-record"}), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported TrialRecord schema_version: None"):
        read_trial_record(path)


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


def test_mkdir_durable_applies_mode_only_to_created_directories(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing"
    existing.mkdir(mode=0o750)
    existing.chmod(0o750)
    target = existing / "run" / "state"

    mkdir_durable(target, created_mode=0o700)

    assert stat.S_IMODE(existing.stat().st_mode) == 0o750
    assert stat.S_IMODE((existing / "run").stat().st_mode) == 0o700
    assert stat.S_IMODE(target.stat().st_mode) == 0o700


def test_mkdir_durable_does_not_change_a_directory_created_concurrently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    concurrent = tmp_path / "concurrent"
    target = concurrent / "owned"
    original_mkdir = Path.mkdir
    intervened = False

    def mkdir_with_concurrent_creator(
        path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        nonlocal intervened
        if path == concurrent and not intervened:
            intervened = True
            original_mkdir(path)
            path.chmod(0o755)
        original_mkdir(
            path,
            mode=mode,
            parents=parents,
            exist_ok=exist_ok,
        )

    monkeypatch.setattr(Path, "mkdir", mkdir_with_concurrent_creator)

    mkdir_durable(target, created_mode=0o700)

    assert stat.S_IMODE(concurrent.stat().st_mode) == 0o755
    assert stat.S_IMODE(target.stat().st_mode) == 0o700


def test_mkdir_durable_rejects_an_existing_non_directory(tmp_path: Path) -> None:
    target = tmp_path / "not-a-directory"
    target.write_bytes(b"file")

    with pytest.raises(FileExistsError):
        mkdir_durable(target)
