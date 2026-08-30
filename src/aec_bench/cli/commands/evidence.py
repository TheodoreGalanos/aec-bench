# ABOUTME: Exposes explicit evidence-index rebuild and portable-evidence verification commands.
# ABOUTME: Emits structured results while keeping portable evidence files authoritative.

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

import typer

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import console, emit
from aec_bench.ledger.durability import fsync_directory

app = typer.Typer(help="Rebuild and verify portable benchmark evidence.")
index_app = typer.Typer(help="Manage the disposable evidence query index.")
app.add_typer(index_app, name="index")


@index_app.command("rebuild")
def rebuild_index(
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Portable evidence ledger directory"),
    database: Path | None = typer.Option(None, "--database", help="SQLite evidence index path"),
) -> None:
    """Rebuild the SQLite evidence index from portable TrialRecord metadata."""

    start = time.monotonic()
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)
    database_path = database or resolved_ledger / "evidence-index.sqlite"
    from aec_bench.ledger.index import EvidenceIndex, EvidenceIndexSchemaError

    try:
        try:
            index = EvidenceIndex(database_path)
        except EvidenceIndexSchemaError:
            report = _rebuild_index_atomically(EvidenceIndex, database_path, resolved_ledger)
        else:
            report = index.rebuild(resolved_ledger)
    except (OSError, ValueError, RuntimeError) as error:
        emit("evidence index rebuild", data=None, errors=[str(error)], start_time=start)
        return
    data = {
        "ledger_root": str(resolved_ledger),
        "database": str(database_path),
        "indexed": report.indexed,
        "unreadable": report.unreadable,
        "conflicts": report.conflicts,
        "generation": report.generation,
        "errors": list(report.errors),
    }
    emit("evidence index rebuild", data, errors=list(report.errors), start_time=start, human_renderer=_render_report)


def _rebuild_index_atomically(index_type: type[Any], database_path: Path, ledger_root: Path) -> Any:
    """Build a fresh index beside the target, then publish it as one SQLite file."""

    target = Path(database_path).expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        report = index_type(temporary).rebuild(ledger_root)
        _checkpoint_sqlite(temporary)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        _remove_sqlite_sidecars(target)
        fsync_directory(target.parent)
        return report
    finally:
        temporary.unlink(missing_ok=True)
        _remove_sqlite_sidecars(temporary)


def _checkpoint_sqlite(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode = DELETE")
    finally:
        connection.close()


def _remove_sqlite_sidecars(database_path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        database_path.with_name(database_path.name + suffix).unlink(missing_ok=True)


@app.command("verify")
def verify_evidence_command(
    run_id: str | None = typer.Option(None, "--run", help="Verify only this exact run ID"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Portable evidence ledger directory"),
) -> None:
    """Verify structured evidence and referenced artifact bytes."""

    start = time.monotonic()
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)
    from aec_bench.ledger.verification import verify_evidence

    try:
        report = verify_evidence(resolved_ledger, run_id=run_id)
    except (OSError, ValueError, RuntimeError) as error:
        emit("evidence verify", data=None, errors=[str(error)], start_time=start)
        return
    data = {
        "ledger_root": str(resolved_ledger),
        "run_id": run_id,
        "records": report.records,
        "receipts": report.receipts,
        "finalizations": report.finalizations,
        "artifacts": report.artifacts,
        "errors": list(report.errors),
    }
    emit("evidence verify", data, errors=list(report.errors), start_time=start, human_renderer=_render_report)


def _render_report(data: dict[str, Any]) -> None:
    from rich.table import Table

    table = Table(title="Evidence operation")
    table.add_column("Field")
    table.add_column("Value")
    for key, value in data.items():
        if key != "errors":
            table.add_row(key, str(value))
    for error in data.get("errors", []):
        table.add_row("error", str(error))
    console.print(table)


__all__ = ("app", "index_app")
