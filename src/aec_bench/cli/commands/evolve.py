# ABOUTME: CLI commands for the evolution domain — init, run, and history.
# ABOUTME: Manages workspaces, runs evolution loops, shows timelines, and rolls back versions.

from __future__ import annotations

import json
import time
from pathlib import Path

import typer
import yaml

from aec_bench.cli.optional_dependencies import require_optional_extra
from aec_bench.cli.output import console, emit

app = typer.Typer(help="Evolve agent workspaces through automated improvement loops.")


@app.command("init")
def evolve_init(
    workspace_path: str = typer.Argument(help="Path for the new workspace directory"),
    name: str = typer.Option(..., "--name", "-n", help="Workspace name"),
    adapter: str = typer.Option("rlm", "--adapter", "--harness", "-a", help="Agent harness (rlm, tool_loop)"),
) -> None:
    """Scaffold a new evolution workspace with manifest and system prompt."""
    start = time.monotonic()
    ws_path = Path(workspace_path)

    if (ws_path / "manifest.yaml").exists():
        emit(
            "evolve init",
            data=None,
            errors=[f"Workspace already exists: {ws_path}"],
            start_time=start,
        )
        raise typer.Exit(1)

    ws_path.mkdir(parents=True, exist_ok=True)
    (ws_path / "prompts").mkdir(exist_ok=True)
    (ws_path / "skills").mkdir(exist_ok=True)

    manifest = {
        "schema_version": 1,
        "name": name,
        "agent_adapter": adapter,
        "evolvable_layers": ["prompts", "skills"],
    }
    (ws_path / "manifest.yaml").write_text(yaml.dump(manifest, default_flow_style=False))
    (ws_path / "prompts" / "system.md").write_text(
        "You are an expert engineering agent. Solve the task carefully and verify your work.\n"
    )

    console.print(f"[bold green]Workspace initialised:[/bold green] {ws_path}")
    console.print(f"  manifest.yaml — name={name}, adapter={adapter}")
    console.print("  prompts/system.md — default prompt")
    console.print("  skills/ — empty")
    emit(
        "evolve init",
        {"workspace_path": str(ws_path), "name": name, "adapter": adapter},
        start_time=start,
    )


@app.command("run")
def evolve_run(
    config_path: Path = typer.Option(..., "--config", "-c", help="Path to evolution YAML config"),
    tasks_root: Path | None = typer.Option(None, "--tasks-root", "-t", help="Root directory containing tasks"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable detailed logging from the evolution engine"),
) -> None:
    """Run an evolution loop from a YAML configuration file."""
    import logging

    # Configure logging so evolution application and backend messages are visible.
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy libraries unless verbose
    if not verbose:
        for noisy in (
            "httpx",
            "httpcore",
            "botocore",
            "botocore.tokens",
            "urllib3",
            "pydantic_ai",
            "numba",
            "numba.core",
        ):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    start = time.monotonic()

    if not config_path.exists():
        emit(
            "evolve run",
            data=None,
            errors=[f"Config not found: {config_path}"],
            start_time=start,
        )
        raise typer.Exit(1)

    require_optional_extra("Evolution execution support", "evolution,local-agents", ("numpy", "ribs", "pydantic_ai"))

    from aec_bench.communication.evolution_report import write_evolution_report
    from aec_bench.evolution import run_evolution_from_config
    from aec_bench.evolution.config_loader import (
        load_evolution_config,
        resolve_task_dirs,
    )

    try:
        config = load_evolution_config(config_path)
    except Exception as exc:
        emit(
            "evolve run",
            data=None,
            errors=[f"Invalid config: {exc}"],
            start_time=start,
        )
        raise typer.Exit(1) from exc

    console.print(f"[bold]Evolution config loaded:[/bold] {config_path}")
    console.print(f"  Workspace: {config.workspace_path}")
    console.print(f"  Classifier: {config.models.classifier}")
    console.print(f"  Evolver: {config.models.evolver}")
    console.print(f"  Backend: {config.backend}")
    console.print(f"  Batch size: {config.batch_size}, Max cycles: {config.max_cycles}")

    if tasks_root is not None:
        task_dirs = resolve_task_dirs(config.task_selector, tasks_root)
        console.print(f"  Tasks resolved: {len(task_dirs)}")
    else:
        console.print("  [yellow]No --tasks-root provided, using stub solve function[/yellow]")

    console.print()
    console.print("[bold]Starting evolution loop...[/bold]")
    console.print("\u2500" * 60)

    try:
        result = run_evolution_from_config(
            config=config,
            tasks_root=tasks_root,
            report_writer=write_evolution_report,
        )
    except Exception as exc:
        emit(
            "evolve run",
            data=None,
            errors=[f"Evolution failed: {exc}"],
            start_time=start,
        )
        raise typer.Exit(1) from exc

    console.print("\u2500" * 60)
    console.print()
    console.print("[bold green]Evolution complete![/bold green]")
    console.print(f"  Cycles: {result.cycles_completed}")
    console.print(f"  Best score: {result.best_score:.1%}")
    console.print(f"  Final score: {result.final_score:.1%}")
    console.print(f"  Best candidate: {result.best_candidate_id}")
    console.print(f"  Converged: {result.converged}")
    console.print(f"  Total trials: {result.total_trials}")

    emit(
        "evolve run",
        {
            "run_id": result.run_id,
            "cycles_completed": result.cycles_completed,
            "best_score": result.best_score,
            "final_score": result.final_score,
            "best_candidate_id": result.best_candidate_id,
            "converged": result.converged,
            "total_trials": result.total_trials,
        },
        start_time=start,
    )


@app.command("history")
def evolve_history(
    workspace_path: str = typer.Argument(help="Path to the evolution workspace"),
) -> None:
    """Show the evolution timeline for a workspace, grouped by run."""
    start = time.monotonic()
    ws_path = Path(workspace_path)

    if not (ws_path / "manifest.yaml").exists():
        emit(
            "evolve history",
            data=None,
            errors=[f"Not a workspace: {ws_path}"],
            start_time=start,
        )
        raise typer.Exit(1)

    from aec_bench.evolution.report_data import list_runs
    from aec_bench.evolution.workspace import Workspace, WorkspaceError

    try:
        workspace = Workspace(ws_path)
    except WorkspaceError as exc:
        emit("evolve history", data=None, errors=[str(exc)], start_time=start)
        raise typer.Exit(1) from exc

    try:
        runs = list_runs(ws_path)
    except WorkspaceError as exc:
        emit("evolve history", data=None, errors=[str(exc)], start_time=start)
        raise typer.Exit(1) from exc

    if not runs:
        console.print("[yellow]No evolution history found. Run 'aec-bench evolve run' first.[/yellow]")
        emit("evolve history", {"runs": []}, start_time=start)
        return

    console.print(f"[bold]{workspace.manifest.name}[/bold] — {len(runs)} run(s)\n")

    for run in runs:
        run_id = run["run_id"]
        strategy = run["strategy"]
        cycles = run["cycles"]
        best = run["best_score"]

        strategy_label = f" ({strategy})" if strategy != "unknown" else ""
        console.print(f"[bold]Run {run_id}[/bold]{strategy_label} — {cycles} cycle(s), best: {best:.1%}")

        # List individual candidates in this run.
        try:
            candidates = workspace.list_candidates(run_id=run_id)
            for candidate in candidates:
                if candidate.candidate_id == "baseline":
                    continue
                label = f" [{candidate.label}]" if candidate.label else ""
                summary = candidate.summary or ""
                committed_at = workspace.candidate_commit_time(candidate.candidate_id).isoformat()
                console.print(f"  {candidate.candidate_id}{label} @ {committed_at}: {summary}")
        except WorkspaceError:
            pass

        console.print()

    emit(
        "evolve history",
        {"workspace": str(ws_path), "run_count": len(runs)},
        start_time=start,
    )


@app.command("rollback")
def evolve_rollback(
    workspace_path: str = typer.Argument(help="Path to the evolution workspace"),
    candidate: str = typer.Argument(help="Candidate ID or immutable label to restore"),
) -> None:
    """Restore workspace source from a candidate as a new commit."""
    start = time.monotonic()
    ws_path = Path(workspace_path)

    if not (ws_path / "manifest.yaml").exists():
        emit(
            "evolve rollback",
            data=None,
            errors=[f"Not a workspace: {ws_path}"],
            start_time=start,
        )
        raise typer.Exit(1)

    from aec_bench.evolution.workspace import Workspace, WorkspaceError

    try:
        workspace = Workspace(ws_path)
    except WorkspaceError as exc:
        emit("evolve rollback", data=None, errors=[str(exc)], start_time=start)
        raise typer.Exit(1) from exc

    try:
        resolved = workspace.resolve_candidate(candidate)
        workspace.rollback_to_candidate(resolved.candidate_id)
    except WorkspaceError as exc:
        emit("evolve rollback", data=None, errors=[str(exc)], start_time=start)
        raise typer.Exit(1) from exc

    console.print(f"[bold green]Restored candidate {resolved.candidate_id}[/bold green]")
    console.print("  A new commit was created — history is preserved.")
    console.print(f"  Use 'aec-bench evolve history {workspace_path}' to verify.")

    emit(
        "evolve rollback",
        {"workspace": str(ws_path), "candidate_id": resolved.candidate_id},
        start_time=start,
    )


@app.command("migrate-workspace")
def evolve_migrate_workspace(
    workspace_path: str = typer.Argument(help="Path to the legacy evolution workspace"),
    plan_path: Path = typer.Option(..., "--plan", help="Path to the explicit migration plan JSON"),
) -> None:
    """Register legacy labels as candidates with explicit source and lineage."""
    start = time.monotonic()
    ws_path = Path(workspace_path)

    from aec_bench.contracts.evolution import WorkspaceMigrationPlan
    from aec_bench.evolution.workspace import Workspace, WorkspaceError

    try:
        plan = WorkspaceMigrationPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        report = Workspace(ws_path).migrate_legacy_versions(plan)
    except (OSError, ValueError, WorkspaceError) as exc:
        emit("evolve migrate-workspace", data=None, errors=[str(exc)], start_time=start)
        raise typer.Exit(1) from exc

    data = report.model_dump(mode="json")
    if not report.complete:
        for issue in report.issues:
            console.print(f"[red]{issue.code}[/red] {issue.label}: {issue.message}")
        emit(
            "evolve migrate-workspace",
            data=data,
            errors=["Legacy workspace migration needs an unambiguous plan."],
            start_time=start,
        )
        raise typer.Exit(1)

    console.print(f"[bold green]Migrated {len(report.migrated_candidate_ids)} candidate(s).[/bold green]")
    console.print(json.dumps(data, indent=2))
    emit("evolve migrate-workspace", data=data, start_time=start)
