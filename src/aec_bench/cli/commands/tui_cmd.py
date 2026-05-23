# ABOUTME: CLI command that launches the unified aec-bench TUI application.
# ABOUTME: Entry point for interactive browsing, trace viewing, and review workflows.

import typer

from aec_bench.cli.commands.config import resolve_path


def launch_tui(
    experiment_id: str | None = typer.Option(
        None,
        "--experiment-id",
        "-e",
        help="Jump to experiment",
    ),
    reviewer_id: str | None = typer.Option(
        None,
        "--reviewer-id",
        "-r",
        help="Enable review mode",
    ),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks directory"),
    feedback_root: str | None = typer.Option(None, "--feedback-root", help="Feedback directory"),
    datasets_root: str | None = typer.Option(None, "--datasets-root", help="Datasets directory"),
) -> None:
    """Launch the interactive terminal UI for browsing, viewing, and reviewing trials."""
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)
    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)
    resolved_feedback = resolve_path("feedback_root", cli_override=feedback_root)
    resolved_datasets = resolve_path("datasets_root", cli_override=datasets_root)

    from aec_bench.config import load_config
    from aec_bench.tui.app import AecBenchTUI

    project_root = load_config().project_root

    app = AecBenchTUI(
        ledger_root=resolved_ledger,
        tasks_root=resolved_tasks,
        feedback_root=resolved_feedback,
        experiment_id=experiment_id,
        reviewer_id=reviewer_id,
        datasets_root=resolved_datasets,
        project_root=project_root,
    )
    app.run()
