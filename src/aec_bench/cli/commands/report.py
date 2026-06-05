# ABOUTME: CLI report commands for experiment analysis and reporting.
# ABOUTME: Wraps communication and evaluation surfaces with formatted output.

import time
from pathlib import Path

import typer

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import console, emit, print_success

app = typer.Typer(help="Generate reports and analysis from ledger data.")


@app.command("summary")
def summary(
    experiment_id: str | None = typer.Option(
        None,
        "--experiment-id",
        "-e",
        help="Filter by experiment",
    ),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
) -> None:
    """Summarize experiment results.

    Returns: n_trials, mean_reward, total_cost_usd, by_adapter breakdown
    (n_trials, mean_reward per adapter).

    Examples:
      aec-bench report summary --experiment-id exp-001
      aec-bench --json report summary -e exp-001 | jq '.data.mean_reward'
    """
    start = time.monotonic()
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)

    from aec_bench.evaluation.pipeline import summarize_evaluation_records
    from aec_bench.ledger.api import query_ledger

    records = query_ledger(resolved_ledger, experiment_id=experiment_id)

    if not records:
        emit("report summary", data=None, errors=["no trial records found"], start_time=start)
        return

    result = summarize_evaluation_records(records)

    def _render(d: dict) -> None:
        console.print(f"[bold]Experiment Summary[/bold] ({d['n_trials']} trials)")
        console.print(f"  Mean reward: [green]{d['mean_reward']:.3f}[/green]")
        console.print(f"  Total cost:  ${d.get('total_cost_usd', 0):.2f}")

        by_adapter = d.get("by_adapter", {})
        if by_adapter:
            from rich.table import Table

            table = Table(title="By Adapter")
            table.add_column("Adapter")
            table.add_column("Trials", justify="right")
            table.add_column("Mean Reward", justify="right")

            for adapter_name, metrics in sorted(by_adapter.items()):
                table.add_row(
                    adapter_name,
                    str(metrics.get("n_trials", 0)),
                    f"{metrics.get('mean_reward', 0):.3f}",
                )

            console.print(table)

    emit("report summary", result, start_time=start, human_renderer=_render)


@app.command("leaderboard")
def leaderboard(
    experiment_id: str | None = typer.Option(
        None,
        "--experiment-id",
        "-e",
        help="Filter by experiment",
    ),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks directory"),
) -> None:
    """Build a leaderboard across experiments.

    Returns: leaderboard.entries list, each with agent_name, model_name,
    n_trials, mean_reward, perfect_trial_rate, total_cost_usd.

    Examples:
      aec-bench report leaderboard --experiment-id exp-001
      aec-bench --json report leaderboard | jq '.data.leaderboard.entries[]'
    """
    start = time.monotonic()
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)
    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)

    from aec_bench.communication.standalone import build_leaderboard_artifact

    artifact = build_leaderboard_artifact(
        ledger_root=resolved_ledger,
        tasks_root=resolved_tasks,
        experiment_id=experiment_id,
        scope="public",
    )

    entries = artifact.get("leaderboard", {}).get("entries", [])
    if not entries:
        emit(
            "report leaderboard",
            data=None,
            errors=["no leaderboard entries found"],
            start_time=start,
        )
        return

    def _render(d: dict) -> None:
        from rich.table import Table

        rows = d.get("leaderboard", {}).get("entries", [])
        table = Table(title="Leaderboard")
        table.add_column("Agent")
        table.add_column("Model")
        table.add_column("Trials", justify="right")
        table.add_column("Mean Reward", justify="right")
        table.add_column("Perfect %", justify="right")
        table.add_column("Cost USD", justify="right")

        for entry in rows:
            table.add_row(
                entry.get("agent_name", ""),
                entry.get("model_name", ""),
                str(entry.get("n_trials", 0)),
                f"{entry.get('mean_reward', 0):.3f}",
                f"{entry.get('perfect_trial_rate', 0):.1%}",
                f"${entry.get('total_cost_usd', 0):.2f}",
            )

        console.print(table)

    emit("report leaderboard", artifact, start_time=start, human_renderer=_render)


@app.command("traces")
def traces(
    experiment_id: str = typer.Option(..., "--experiment-id", "-e", help="Experiment ID"),
    output_path: Path | None = typer.Option(None, "--output", "-o", help="Output JSON file"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
) -> None:
    """Export trace summaries for review tooling.

    Returns: list of trace summaries, each with trial_id, task_id, n_turns,
    reward.

    Examples:
      aec-bench report traces --experiment-id exp-001 --output traces.json
      aec-bench --json report traces -e exp-001 | jq '.data[].n_turns'
    """
    start = time.monotonic()
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)

    from aec_bench.communication.trace_report import (
        build_trace_summaries,
        export_trace_summaries_json,
    )
    from aec_bench.ledger.api import query_ledger

    records = query_ledger(resolved_ledger, experiment_id=experiment_id)

    if not records:
        emit("report traces", data=None, errors=["no trial records found"], start_time=start)
        return

    summaries = build_trace_summaries(records)
    data = [s.to_dict() for s in summaries]

    if output_path:
        export_trace_summaries_json(summaries, output_path)
        print_success(f"Exported {len(summaries)} trace summaries to {output_path}")

    def _render(d: list) -> None:
        from rich.table import Table

        table = Table(title=f"Trace Summaries ({len(d)} trials)")
        table.add_column("Trial ID", style="dim")
        table.add_column("Task")
        table.add_column("Turns", justify="right")
        table.add_column("Reward", justify="right")

        for entry in d:
            reward = entry.get("reward", 0)
            reward_style = "green" if reward >= 1.0 else "red" if reward == 0.0 else "yellow"
            table.add_row(
                str(entry.get("trial_id", ""))[:20],
                str(entry.get("task_id", "")),
                str(entry.get("n_turns", "—")),
                f"[{reward_style}]{reward:.3f}[/{reward_style}]",
            )

        console.print(table)

    emit("report traces", data, start_time=start, human_renderer=_render)


@app.command("behavioral")
def behavioral(
    experiment_id: str = typer.Option(..., "--experiment-id", "-e", help="Experiment ID"),
    classifier: str = typer.Option(..., "--classifier", help="Model for behavioral classification"),
    output_path: Path | None = typer.Option(None, "--output", "-o", help="Output JSON file"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
) -> None:
    """Run behavioral analysis over experiment trials.

    Returns: classifier_model, trials list with behavioral classifications
    per trial.

    Examples:
      aec-bench report behavioral -e exp-001 --classifier claude-sonnet-4-20250514
      aec-bench --json report behavioral -e exp-001 \\
        --classifier claude-sonnet-4-20250514 | jq '.data.trials'
    """
    start = time.monotonic()
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)

    from aec_bench.communication.behavioral_report import (
        build_behavioral_export,
        export_behavioral_report_json,
    )
    from aec_bench.evaluation.behavioral import LLMTurnClassifier
    from aec_bench.ledger.api import query_ledger
    from aec_bench.providers.behavioral_llm import build_behavioral_llm_client

    records = query_ledger(resolved_ledger, experiment_id=experiment_id)

    if not records:
        emit("report behavioral", data=None, errors=["no trial records found"], start_time=start)
        return

    with console.status(f"Running behavioral analysis with {classifier}..."):
        llm_client = build_behavioral_llm_client(model=classifier)
        turn_classifier = LLMTurnClassifier(client=llm_client)
        export = build_behavioral_export(records, classifier=turn_classifier)

    data = export.to_dict()

    if output_path:
        export_behavioral_report_json(export, output_path)
        print_success(f"Exported behavioral analysis to {output_path}")

    def _render(d: dict) -> None:
        from rich.table import Table

        table = Table(title="Behavioral Analysis Summary")
        table.add_column("Metric")
        table.add_column("Value", justify="right")

        n_trials = len(d.get("trials", []))
        table.add_row("Trials analysed", str(n_trials))
        table.add_row("Classifier", d.get("classifier_model", "—"))

        console.print(table)

    emit("report behavioral", data, start_time=start, human_renderer=_render)
