# ABOUTME: CLI ledger commands for querying and exporting trial records.
# ABOUTME: Wraps ledger.api with formatted terminal output.

import time
from pathlib import Path

import typer

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import console, emit, print_success

app = typer.Typer(help="Query and export ledger trial records.")


@app.command("list")
def list_trials(
    experiment_id: str | None = typer.Option(
        None,
        "--experiment-id",
        "-e",
        help="Filter by experiment",
    ),
    task_prefix: str | None = typer.Option(None, "--task-prefix", help="Filter by task prefix"),
    adapter: str | None = typer.Option(None, "--adapter", "--harness", help="Filter by harness"),
    model: str | None = typer.Option(None, "--model", help="Filter by model"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
) -> None:
    """List trial records in the ledger.

    Returns: list of trials, each with trial_id, experiment_id, task_id,
    model, reward.

    Examples:
      aec-bench ledger list --experiment-id exp-001
      aec-bench ledger list --adapter tool_loop --json | jq '.data[].reward'
    """
    start = time.monotonic()
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)

    from aec_bench.ledger.api import query_ledger

    records = query_ledger(
        resolved_ledger,
        experiment_id=experiment_id,
        task_prefix=task_prefix,
        adapter=adapter,
        model=model,
    )

    data = [
        {
            "trial_id": r.trial_id,
            "experiment_id": r.experiment_id,
            "task_id": r.task.task_id,
            "model": r.agent.model,
            "reward": r.evaluation.reward,
        }
        for r in records
    ]

    def _render(d: list) -> None:
        from rich.table import Table

        table = Table(title=f"Ledger: {len(d)} trials")
        table.add_column("Trial ID", style="dim")
        table.add_column("Experiment")
        table.add_column("Task")
        table.add_column("Model")
        table.add_column("Reward", justify="right")

        for row in d:
            reward = row["reward"]
            reward_style = "green" if reward >= 1.0 else "red" if reward == 0.0 else "yellow"
            table.add_row(
                row["trial_id"][:20],
                row["experiment_id"][:20],
                row["task_id"],
                row["model"],
                f"[{reward_style}]{reward:.3f}[/{reward_style}]",
            )

        console.print(table)

    emit("ledger list", data, start_time=start, human_renderer=_render)


@app.command("export")
def export_trials(
    experiment_id: str | None = typer.Option(
        None,
        "--experiment-id",
        "-e",
        help="Filter by experiment",
    ),
    task_prefix: str | None = typer.Option(None, "--task-prefix", help="Filter by task prefix"),
    output_path: Path = typer.Option(..., "--output", "-o", help="Output JSONL file path"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
) -> None:
    """Export trial records to JSONL."""
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)

    from aec_bench.ledger.api import export_trial_records_jsonl

    result_path = export_trial_records_jsonl(
        resolved_ledger,
        output_path=output_path,
        experiment_id=experiment_id,
        task_prefix=task_prefix,
    )

    print_success(f"Exported to {result_path}")
