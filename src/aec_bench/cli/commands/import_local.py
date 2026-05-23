# ABOUTME: Import a local RLM run into the ledger for web viewer display.
# ABOUTME: Creates a TrialRecord from local run artifacts without Harbor.

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import typer

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import console, emit, print_error
from aec_bench.harness.local_import import (
    build_trial_record,
    copy_artifacts,
    find_tasks_root,
)
from aec_bench.ledger.writer import write_trial_record


def import_local_run(
    run_dir: str = typer.Argument(
        help="Path to local run directory (e.g. _local_runs/20260327-083815)",
    ),
    task_path: str = typer.Option(
        ...,
        "--task",
        "-t",
        help="Path to the task directory",
    ),
    experiment_id: str = typer.Option(
        "local",
        "--experiment",
        "-e",
        help="Experiment ID",
    ),
    trial_id: str | None = typer.Option(
        None,
        "--trial-id",
        help="Custom trial ID (auto-generated if omitted)",
    ),
    ledger_root_override: str | None = typer.Option(
        None,
        "--ledger-root",
        help="Ledger directory",
    ),
) -> None:
    """Import a local run into the ledger for web viewer display.

    Examples:
      aec-bench import-local _local_runs/20260327-083815 --task tasks/.../srapc-fee-proposal
    """
    start = time.monotonic()
    run_path = Path(run_dir).resolve()
    task_dir = Path(task_path).resolve()

    if not run_path.is_dir():
        print_error(f"Run directory not found: {run_path}")
        raise typer.Exit(1)

    agent_result_file = run_path / "agent_result.json"
    if not agent_result_file.exists():
        print_error(f"No agent_result.json in {run_path}")
        raise typer.Exit(1)

    if not task_dir.is_dir():
        print_error(f"Task directory not found: {task_dir}")
        raise typer.Exit(1)

    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root_override)

    # Derive trial_id from the run directory timestamp if not provided
    if trial_id is None:
        tasks_root = find_tasks_root(task_dir)
        try:
            task_id_slug = task_dir.relative_to(tasks_root).as_posix().replace("/", "__")
        except ValueError:
            task_id_slug = task_dir.name
        timestamp = run_path.name
        trial_id = f"{task_id_slug}__{timestamp}"

    # Determine repo root (parent of tasks_root for path normalisation)
    tasks_root = find_tasks_root(task_dir)
    repo_root = tasks_root.parent

    # Copy artifacts to a location next to the ledger record
    artifact_dir = resolved_ledger / experiment_id / "_artifacts" / trial_id
    copied = copy_artifacts(run_path, artifact_dir)

    record = build_trial_record(
        run_path=run_path,
        task_dir=task_dir,
        experiment_id=experiment_id,
        trial_id=trial_id,
        artifact_dir=artifact_dir,
        repo_root=repo_root,
    )

    write_trial_record(ledger_root=resolved_ledger, record=record)

    data = {
        "experiment_id": experiment_id,
        "trial_id": trial_id,
        "model": record.agent.model,
        "tokens_in": record.cost.tokens_in if record.cost else None,
        "tokens_out": record.cost.tokens_out if record.cost else None,
        "estimated_cost_usd": record.cost.estimated_cost_usd if record.cost else None,
        "artifacts": copied,
        "viewer_url": f"http://127.0.0.1:8710/viewer/{experiment_id}/{trial_id}",
    }

    def _render(d: dict[str, Any]) -> None:
        console.print("[bold]Imported local run into ledger[/bold]")
        console.print(f"  Experiment: {d['experiment_id']}")
        console.print(f"  Trial: {d['trial_id']}")
        console.print(f"  Model: {d['model']}")
        tokens_in = d.get("tokens_in") or 0
        tokens_out = d.get("tokens_out") or 0
        console.print(f"  Tokens: {tokens_in:,} in / {tokens_out:,} out")
        cost = d.get("estimated_cost_usd")
        if cost is not None:
            console.print(f"  Cost: ${cost:.2f}")
        console.print(f"  Artifacts: {', '.join(d['artifacts'])}")
        console.print(f"\n  View at: {d['viewer_url']}")

    emit("import-local", data, start_time=start, human_renderer=_render)
