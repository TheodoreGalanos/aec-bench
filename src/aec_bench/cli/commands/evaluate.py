# ABOUTME: CLI evaluate command for analysing experiment results and persisting artifacts.
# ABOUTME: Wires the evaluation pipeline with Rich tables, JSON output, and HTML report generation.

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer

from aec_bench import __version__
from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import console, emit


def evaluate_experiment(
    experiment: Annotated[
        str,
        typer.Option("--experiment", "-e", help="Experiment ID to evaluate"),
    ],
    report: Annotated[
        Path | None,
        typer.Option("--report", help="Path for standalone HTML report"),
    ] = None,
    adapter: Annotated[
        str | None,
        typer.Option("--adapter", "--harness", help="Filter trials by harness"),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="Filter trials by model name"),
    ] = None,
    task_prefix: Annotated[
        str | None,
        typer.Option("--task-prefix", help="Filter trials by task ID prefix"),
    ] = None,
    ledger_root: Annotated[
        str | None,
        typer.Option("--ledger-root", help="Ledger directory"),
    ] = None,
) -> None:
    """Evaluate an experiment: compute summary stats, persist artifact, display results.

    Returns: evaluation_id, experiment_id, timestamp, filters, summary
    (mean_reward, n_trials, total_cost_usd), by_adapter breakdown
    (n_trials, mean_reward, perfect_rate, zero_rate, total_cost_usd per adapter),
    by_task_prefix breakdown, framework_version.

    Examples:
      aec-bench evaluate --experiment exp-001 --ledger-root jobs/
      aec-bench --json evaluate --experiment exp-001 | jq '.data.summary'
    """
    from aec_bench.communication.html_report import build_evaluation_report
    from aec_bench.evaluation.artifact import (
        EvaluationArtifact,
        EvaluationFilters,
        write_evaluation_artifact,
    )
    from aec_bench.evaluation.pipeline import summarize_evaluation_records
    from aec_bench.ledger.api import query_ledger

    start = time.monotonic()
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)

    records = query_ledger(
        resolved_ledger,
        experiment_id=experiment,
        adapter=adapter,
        model=model,
        task_prefix=task_prefix,
    )

    if not records:
        emit(
            "evaluate",
            data=None,
            errors=[f"no trial records found for experiment '{experiment}'"],
            start_time=start,
        )
        return

    summary = summarize_evaluation_records(records)

    by_adapter = summary.get("by_adapter", {})
    by_task = summary.get("by_task_prefix", {})

    # Build and persist artifact
    filters = EvaluationFilters(
        adapter=adapter,
        model=model,
        task_prefix=task_prefix,
    )
    artifact = EvaluationArtifact(
        evaluation_id=f"eval-{uuid4().hex[:12]}",
        experiment_id=experiment,
        timestamp=datetime.now(tz=UTC),
        filters=filters,
        summary=summary,
        behavioral=None,
        framework_version=__version__,
    )
    write_evaluation_artifact(resolved_ledger, artifact)

    if report is not None:
        build_evaluation_report(artifact, report)
        console.print(f"[green]Report written to {report}[/green]")

    def _render_evaluate(data: dict) -> None:
        _print_overview_table(experiment, summary)
        _print_adapter_table(by_adapter)
        _print_task_table(by_task)

    emit(
        "evaluate",
        artifact.model_dump(),
        start_time=start,
        human_renderer=_render_evaluate,
    )


def _print_overview_table(experiment_id: str, summary: dict) -> None:
    """Print the overview Rich table."""
    from rich.table import Table

    table = Table(title=f"Evaluation: {experiment_id}")
    table.add_column("Metric")
    table.add_column("Value", justify="right")

    table.add_row("Total Trials", str(summary.get("n_trials", 0)))
    table.add_row("Mean Reward", f"{summary.get('mean_reward', 0):.3f}")
    table.add_row("Total Cost", f"${summary.get('total_cost_usd', 0):.2f}")

    console.print(table)


def _print_adapter_table(by_adapter: dict) -> None:
    """Print the by-adapter Rich table."""
    if not by_adapter:
        return
    from rich.table import Table

    table = Table(title="By Adapter")
    table.add_column("Adapter")
    table.add_column("Trials", justify="right")
    table.add_column("Mean Reward", justify="right")
    table.add_column("Perfect %", justify="right")
    table.add_column("Zero %", justify="right")
    table.add_column("Cost", justify="right")

    for name, metrics in sorted(by_adapter.items()):
        table.add_row(
            name,
            str(metrics.get("n_trials", 0)),
            f"{metrics.get('mean_reward', 0):.3f}",
            f"{metrics.get('perfect_rate', 0):.1%}",
            f"{metrics.get('zero_rate', 0):.1%}",
            f"${metrics.get('total_cost_usd', 0):.2f}",
        )

    console.print(table)


def _print_task_table(by_task: dict) -> None:
    """Print the by-task-prefix Rich table."""
    if not by_task:
        return
    from rich.table import Table

    table = Table(title="By Task Prefix")
    table.add_column("Task Prefix")
    table.add_column("Trials", justify="right")
    table.add_column("Mean Reward", justify="right")
    table.add_column("Perfect %", justify="right")
    table.add_column("Zero %", justify="right")
    table.add_column("Cost", justify="right")

    for name, metrics in sorted(by_task.items()):
        table.add_row(
            name,
            str(metrics.get("n_trials", 0)),
            f"{metrics.get('mean_reward', 0):.3f}",
            f"{metrics.get('perfect_rate', 0):.1%}",
            f"{metrics.get('zero_rate', 0):.1%}",
            f"${metrics.get('total_cost_usd', 0):.2f}",
        )

    console.print(table)
