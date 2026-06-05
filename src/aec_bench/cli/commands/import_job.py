# ABOUTME: CLI import command for bringing Harbor job results into the ledger.
# ABOUTME: Wraps harbor_import and experiment_runner with progress output.

import time
from pathlib import Path

import typer

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import console, emit, print_success


def import_job(
    job_dir: Path = typer.Argument(..., help="Path to Harbor job directory"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks directory"),
) -> None:
    """Import a Harbor job directory into the ledger.

    Returns: job_dir, discovered, imported, duplicates.

    Examples:
      aec-bench import jobs/exp-001-run-1
      aec-bench --json import jobs/exp-001-run-1 | jq '.data.imported'
    """
    start = time.monotonic()
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)
    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)

    if not job_dir.exists():
        emit("import", data=None, errors=[f"job directory not found: {job_dir}"], start_time=start)
        return

    from aec_bench.harness.harbor_import import import_harbor_job
    from aec_bench.ledger.writer import DuplicateTrialRecordError, write_trial_record

    with console.status("Importing Harbor job..."):
        repo_root = resolved_tasks.parent
        records = import_harbor_job(job_dir=job_dir, repo_root=repo_root)

    imported = 0
    duplicates = 0
    for record in records:
        try:
            write_trial_record(ledger_root=resolved_ledger, record=record)
            imported += 1
        except DuplicateTrialRecordError:
            duplicates += 1

    data = {
        "job_dir": str(job_dir),
        "discovered": len(records),
        "imported": imported,
        "duplicates": duplicates,
    }

    def _render(d: dict) -> None:
        print_success(
            f"Imported {d['imported']} trials ({d['duplicates']} duplicates skipped) from {d['discovered']} discovered"
        )

    emit("import", data, start_time=start, human_renderer=_render)
