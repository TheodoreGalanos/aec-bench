# ABOUTME: Maintains a disposable SQLite index of portable TrialRecord metadata.
# ABOUTME: Rebuilds index rows from authoritative ledger files without reading evidence bodies.

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import NamedTuple, cast

from aec_bench.contracts.dataset import dataset_reference_key
from aec_bench.contracts.trial_record import RunManifest, TrialRecord
from aec_bench.ledger.reader import _iter_trial_record_paths
from aec_bench.ledger.writer import run_manifest_path

EVIDENCE_INDEX_SCHEMA_VERSION = 1


class EvidenceIndexError(RuntimeError):
    """Base error for the disposable evidence query index."""


class EvidenceIndexSchemaError(EvidenceIndexError):
    """Reject an index database that does not use the current schema."""


class EvidenceIndexRow(NamedTuple):
    """One queryable TrialRecord summary; portable record bytes remain outside SQLite."""

    trial_id: str
    run_id: str
    experiment_id: str
    task_id: str
    task_revision: str
    task_kind: str
    adapter: str
    model: str
    world_profile_id: str | None
    dataset_id: str | None
    reward: float | None
    attempt: int
    execution_status: str
    evaluation_status: str
    evidence_status: str
    started_at: datetime
    completed_at: datetime | None
    provider_evidence_present: bool
    record_path: str
    record_sha256: str


class EvidenceIndexRebuildReport(NamedTuple):
    """Outcome of one scan and replacement of the disposable index contents."""

    indexed: int
    unreadable: int
    conflicts: int
    generation: int
    errors: tuple[str, ...]


class EvidenceIndex:
    """Rebuild and query a SQLite metadata index for one portable ledger root."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    @property
    def generation(self) -> int:
        """Return the current rebuild generation used to bind cursors."""

        connection = self._connect()
        try:
            row = connection.execute("SELECT generation FROM evidence_index_metadata WHERE singleton = 1").fetchone()
            if row is None:
                raise EvidenceIndexSchemaError("evidence index metadata is missing")
            return int(row[0])
        finally:
            connection.close()

    def rebuild(self, ledger_root: Path) -> EvidenceIndexRebuildReport:
        """Replace index rows from valid portable records and leave ledger files unchanged."""

        selected_root = Path(ledger_root)
        rows: dict[str, EvidenceIndexRow] = {}
        conflicted_ids: set[str] = set()
        unreadable = 0
        conflicts = 0
        errors: list[str] = []
        for record_path in _iter_trial_record_paths(selected_root):
            if _is_run_metadata_path(selected_root, record_path):
                continue
            try:
                _validate_record_path(selected_root, record_path)
                payload = record_path.read_bytes()
                record = TrialRecord.model_validate_json(payload)
                manifest = _read_manifest(selected_root, record_path, record.run_id)
                _validate_reference_locations(selected_root, record_path, record)
                row = _index_row(record, manifest, record_path, selected_root, payload)
            except (OSError, ValueError, TypeError, RuntimeError) as error:
                unreadable += 1
                errors.append(f"{record_path}: {error}")
                continue
            previous = rows.get(row.trial_id)
            if row.trial_id in conflicted_ids:
                conflicts += 1
                errors.append(f"{record_path}: duplicate trial_id remains quarantined: {row.trial_id}")
                continue
            if previous is not None:
                conflicts += 1
                conflicted_ids.add(row.trial_id)
                rows.pop(row.trial_id, None)
                errors.append(f"{record_path}: duplicate trial_id conflicts with {previous.record_path}")
                continue
            rows[row.trial_id] = row

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM evidence_trial_records")
            connection.executemany(
                """
                INSERT INTO evidence_trial_records (
                    trial_id, run_id, experiment_id, task_id, task_revision, task_kind,
                    adapter, model, world_profile_id, dataset_id, attempt,
                    reward,
                    execution_status, evaluation_status, evidence_status, started_at,
                    completed_at, provider_evidence_present, record_path, record_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (_row_values(row) for row in sorted(rows.values(), key=lambda item: item.trial_id)),
            )
            current_generation = int(
                connection.execute(
                    "SELECT generation FROM evidence_index_metadata WHERE singleton = 1",
                ).fetchone()[0]
            )
            generation = current_generation + 1
            connection.execute(
                "UPDATE evidence_index_metadata SET generation = ? WHERE singleton = 1",
                (generation,),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
        return EvidenceIndexRebuildReport(len(rows), unreadable, conflicts, generation, tuple(errors))

    def _select_rows(
        self,
        where_sql: str,
        parameters: tuple[object, ...],
        limit: int,
        expected_generation: int,
    ) -> tuple[EvidenceIndexRow, ...]:
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            current_generation = int(
                connection.execute(
                    "SELECT generation FROM evidence_index_metadata WHERE singleton = 1",
                ).fetchone()[0]
            )
            if current_generation != expected_generation:
                raise EvidenceIndexError("evidence index changed while the query was starting")
            records = connection.execute(
                f"""
                SELECT trial_id, run_id, experiment_id, task_id, task_revision, task_kind,
                       adapter, model, world_profile_id, dataset_id, reward, attempt,
                       execution_status, evaluation_status, evidence_status, started_at,
                       completed_at, provider_evidence_present, record_path, record_sha256
                FROM evidence_trial_records
                WHERE {where_sql}
                ORDER BY started_at ASC, trial_id ASC
                LIMIT ?
                """,
                (*parameters, limit),
            ).fetchall()
            connection.commit()
            return tuple(_row_from_sql(record) for record in records)
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialise(self) -> None:
        connection = self._connect()
        try:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'",
                )
            }
            if "evidence_index_metadata" in tables:
                if "evidence_trial_records" not in tables:
                    raise EvidenceIndexSchemaError(
                        "incomplete evidence index schema; recreate the disposable SQLite database",
                    )
                row = connection.execute(
                    "SELECT schema_version FROM evidence_index_metadata WHERE singleton = 1",
                ).fetchone()
                if row is None or int(row[0]) != EVIDENCE_INDEX_SCHEMA_VERSION:
                    raise EvidenceIndexSchemaError(
                        "stale evidence index schema; recreate the disposable SQLite database",
                    )
                return
            if tables:
                raise EvidenceIndexSchemaError(
                    "unrecognised evidence index database; recreate the disposable SQLite database",
                )
            connection.executescript(
                f"""
                CREATE TABLE evidence_index_metadata (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    schema_version INTEGER NOT NULL,
                    generation INTEGER NOT NULL CHECK (generation >= 0)
                );
                INSERT INTO evidence_index_metadata (singleton, schema_version, generation)
                VALUES (1, {EVIDENCE_INDEX_SCHEMA_VERSION}, 0);
                CREATE TABLE evidence_trial_records (
                    trial_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_revision TEXT NOT NULL,
                    task_kind TEXT NOT NULL,
                    adapter TEXT NOT NULL,
                    model TEXT NOT NULL,
                    world_profile_id TEXT,
                    dataset_id TEXT,
                    attempt INTEGER NOT NULL CHECK (attempt > 0),
                    reward REAL,
                    execution_status TEXT NOT NULL,
                    evaluation_status TEXT NOT NULL,
                    evidence_status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    provider_evidence_present INTEGER NOT NULL CHECK (provider_evidence_present IN (0, 1)),
                    record_path TEXT NOT NULL UNIQUE,
                    record_sha256 TEXT NOT NULL
                );
                CREATE INDEX evidence_trial_records_run ON evidence_trial_records (run_id, started_at, trial_id);
                CREATE INDEX evidence_trial_records_task ON evidence_trial_records (task_id, task_revision);
                CREATE INDEX evidence_trial_records_model ON evidence_trial_records (model, started_at, trial_id);
                CREATE INDEX evidence_trial_records_status ON evidence_trial_records (
                    execution_status, evaluation_status, started_at, trial_id
                );
                CREATE INDEX evidence_trial_records_profile ON evidence_trial_records (
                    world_profile_id, started_at, trial_id
                );
                """,
            )
            connection.commit()
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection


def _read_manifest(ledger_root: Path, record_path: Path, run_id: str) -> RunManifest:
    locator = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    candidates = [
        run_manifest_path(ledger_root=ledger_root, experiment_id=record_path.parent.name, run_id=run_id),
    ]
    if record_path.parent.name == "trial-records":
        candidates.insert(0, record_path.parent / "_runs" / f"{locator}.json")
    manifest_path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if manifest_path is None:
        raise FileNotFoundError(f"run manifest is missing for run {run_id}")
    if manifest_path.is_symlink():
        raise ValueError("run manifest must not be a symlink")
    manifest_root = record_path.parent if record_path.parent.name == "trial-records" else ledger_root
    if not manifest_path.resolve().is_relative_to(manifest_root.resolve()):
        raise ValueError("run manifest resolves outside the ledger root")
    manifest = RunManifest.model_validate_json(manifest_path.read_bytes())
    if manifest.run_id != run_id:
        raise ValueError("run manifest run_id does not match TrialRecord")
    return manifest


def _validate_reference_locations(ledger_root: Path, record_path: Path, record: TrialRecord) -> None:
    references = [
        *(item.artifact for item in record.extension_refs),
        *(item.artifact for item in record.authority_evidence),
        *(item.artifact for item in record.input.input_files or ()),
        *((item.artifact for item in record.output.artifacts) if record.output is not None else ()),
    ]
    if record.provider_evidence is not None:
        references.append(record.provider_evidence)
    if not references:
        return
    roots = [ledger_root / "_artifacts"]
    if record_path.parent.name == "trial-records":
        roots.insert(0, record_path.parent / "_artifacts")
    for reference in references:
        relative = PurePosixPath(reference.artifact_id)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"artifact reference has unsafe path: {reference.artifact_id}")
        if not any(
            (candidate := root.joinpath(*relative.parts)).is_file()
            and not candidate.is_symlink()
            and candidate.resolve().is_relative_to(root.resolve())
            for root in roots
        ):
            raise FileNotFoundError(f"artifact reference is missing: {reference.artifact_id}")


def _validate_record_path(ledger_root: Path, record_path: Path) -> None:
    root = ledger_root.resolve()
    resolved = record_path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("trial record resolves outside the ledger root")
    relative_parts = record_path.relative_to(ledger_root).parts
    current = ledger_root
    for part in relative_parts:
        current /= part
        if current.is_symlink():
            raise ValueError("trial record path must not contain symlinks")


def _is_run_metadata_path(ledger_root: Path, record_path: Path) -> bool:
    """Exclude non-trial JSON anywhere below a portable evidence run directory."""

    for ancestor in record_path.parents:
        if ancestor == ledger_root.parent:
            break
        trial_records = ancestor / "trial-records"
        if trial_records.is_dir():
            return record_path.parent != trial_records
    return False


def _index_row(
    record: TrialRecord,
    manifest: RunManifest,
    record_path: Path,
    ledger_root: Path,
    payload: bytes,
) -> EvidenceIndexRow:
    release = record.planned_trial_binding.family_release if record.planned_trial_binding is not None else None
    profile_id = None
    if release is not None and release.kind == "world":
        profile_id = release.profile.profile_id
    return EvidenceIndexRow(
        trial_id=record.trial_id,
        run_id=record.run_id,
        experiment_id=manifest.experiment_id,
        task_id=record.task_id,
        task_revision=record.input.task_revision,
        task_kind=record.input.task_kind,
        adapter=manifest.agent.adapter,
        model=manifest.agent.model,
        world_profile_id=profile_id,
        dataset_id=None if manifest.dataset is None else dataset_reference_key(manifest.dataset),
        reward=None if record.evaluation is None else record.evaluation.reward,
        attempt=record.attempt,
        execution_status=record.execution_status.value,
        evaluation_status=record.evaluation_status.value,
        evidence_status=record.evidence_status.value,
        started_at=_canonical_timestamp(record.started_at),
        completed_at=None if record.completed_at is None else _canonical_timestamp(record.completed_at),
        provider_evidence_present=record.provider_evidence is not None,
        record_path=record_path.relative_to(ledger_root).as_posix(),
        record_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _canonical_timestamp(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _row_values(row: EvidenceIndexRow) -> tuple[object, ...]:
    return (
        row.trial_id,
        row.run_id,
        row.experiment_id,
        row.task_id,
        row.task_revision,
        row.task_kind,
        row.adapter,
        row.model,
        row.world_profile_id,
        row.dataset_id,
        row.attempt,
        row.reward,
        row.execution_status,
        row.evaluation_status,
        row.evidence_status,
        row.started_at.isoformat(),
        None if row.completed_at is None else row.completed_at.isoformat(),
        int(row.provider_evidence_present),
        row.record_path,
        row.record_sha256,
    )


def _row_from_sql(row: sqlite3.Row | tuple[object, ...]) -> EvidenceIndexRow:
    return EvidenceIndexRow(
        trial_id=str(row[0]),
        run_id=str(row[1]),
        experiment_id=str(row[2]),
        task_id=str(row[3]),
        task_revision=str(row[4]),
        task_kind=str(row[5]),
        adapter=str(row[6]),
        model=str(row[7]),
        world_profile_id=None if row[8] is None else str(row[8]),
        dataset_id=None if row[9] is None else str(row[9]),
        reward=None if row[10] is None else float(cast(float, row[10])),
        attempt=int(cast(int, row[11])),
        execution_status=str(row[12]),
        evaluation_status=str(row[13]),
        evidence_status=str(row[14]),
        started_at=datetime.fromisoformat(str(row[15])),
        completed_at=None if row[16] is None else datetime.fromisoformat(str(row[16])),
        provider_evidence_present=bool(row[17]),
        record_path=str(row[18]),
        record_sha256=str(row[19]),
    )


__all__ = (
    "EVIDENCE_INDEX_SCHEMA_VERSION",
    "EvidenceIndex",
    "EvidenceIndexError",
    "EvidenceIndexRebuildReport",
    "EvidenceIndexRow",
    "EvidenceIndexSchemaError",
)
