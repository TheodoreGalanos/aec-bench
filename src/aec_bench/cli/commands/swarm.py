# ABOUTME: CLI commands for multi-agent swarm evolution — run, status, and history.
# ABOUTME: Manages swarm lifecycle via the SwarmManager.

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from aec_bench.cli.optional_dependencies import require_optional_extra
from aec_bench.cli.output import console, print_error

app = typer.Typer(help="Multi-agent QD evolution swarm.")


@app.command("run")
def swarm_run(
    config_path: str = typer.Argument(help="Path to swarm.yaml config file"),
    ui: bool = typer.Option(  # noqa: ARG001
        False, "--ui", help="Launch dashboard in browser (fast-follow)"
    ),
) -> None:
    """Start a new swarm run from a config file."""
    path = Path(config_path)
    if not path.exists():
        print_error(f"Config not found: {path}")
        raise typer.Exit(1)
    require_optional_extra("Swarm execution support", "evolution,local-agents", ("numpy", "ribs", "pydantic_ai"))
    try:
        from aec_bench.evolution.swarm.config import load_swarm_config

        config = load_swarm_config(path)
    except Exception as exc:
        print_error(f"Invalid config: {exc}")
        raise typer.Exit(1) from exc

    if config.evaluation.backend != "local":
        print_error(f"Swarm currently supports only local evaluation; configured backend: {config.evaluation.backend}")
        raise typer.Exit(1)

    console.print(f"[bold green]Swarm starting:[/bold green] {config.agents.count} agents")
    console.print(f"  Budget: ${config.budget.max_cost_usd:.2f}")
    console.print(f"  Model: {config.agents.default_model}")

    import asyncio

    from aec_bench.evolution.swarm.evolver import SwarmEvolverFactory
    from aec_bench.evolution.swarm.manager import SwarmManager

    workspace_path = Path(config.task.workspace)
    task_path = Path(config.task.task_path)

    if not workspace_path.exists():
        print_error(f"Workspace not found: {workspace_path}")
        raise typer.Exit(1)

    # Resolve task directories — find all dirs with instruction.md
    task_dirs: list[Path] = []
    if task_path.is_dir():
        for candidate in sorted(task_path.rglob("instruction.md")):
            task_dirs.append(candidate.parent)
    if not task_dirs:
        print_error(f"No tasks found in: {task_path}")
        raise typer.Exit(1)

    console.print(f"  Tasks: {len(task_dirs)} task instances")

    # Read adapter from workspace manifest
    import yaml as _yaml

    raw_manifest: object = _yaml.safe_load((workspace_path / "manifest.yaml").read_text())
    manifest_data = {str(k): v for k, v in raw_manifest.items()} if isinstance(raw_manifest, dict) else {}
    adapter_value = manifest_data.get("agent_adapter", "rlm")
    adapter = adapter_value if isinstance(adapter_value, str) else "rlm"
    console.print(f"  Adapter: {adapter}")

    # Build the classifier client used for enrichment and compaction.
    from aec_bench.providers.behavioral_llm import build_behavioral_llm_client

    classifier_llm = build_behavioral_llm_client(model=config.agents.default_model)

    # Build evolver factory
    factory = SwarmEvolverFactory(
        workspace_source=workspace_path,
        task_dirs=task_dirs,
        classifier_llm=classifier_llm,
        model=config.agents.default_model,
        adapter=adapter,
        timeout=config.evaluation.timeout,
        batch_size=config.evolution.batch_size,
        improvement_threshold=config.evolution.improvement_threshold,
        stagnation_window=5,
        structural_weight=config.evolution.structural_weight,
    )

    state_dir = workspace_path / "_swarm_runs"
    state_dir.mkdir(parents=True, exist_ok=True)

    manager = SwarmManager(
        config=config,
        state_dir=state_dir,
        evolver_factory=factory,
    )

    try:
        result = asyncio.run(manager.run())
        console.print("\n[bold green]Swarm complete![/bold green]")
        console.print(f"  Run ID: {result.run_id}")
        console.print(f"  Evals: {result.total_evals}")
        console.print(f"  Best score: {result.best_score:.2f}")
        console.print(
            f"  Archive: {result.archive_summary.get('size', 0)} entries, "
            f"{result.archive_summary.get('coverage', 0):.0%} coverage"
        )
        console.print(f"  Cost: ${result.total_cost_usd:.2f}")
        console.print(f"  Elapsed: {result.elapsed_seconds:.1f}s")
    finally:
        factory.cleanup()


@app.command("status")
def swarm_status(
    run_id: str = typer.Argument(help="Run ID to check"),
    state_dir: str = typer.Option(".", "--state-dir", help="Directory containing swarm state"),
) -> None:
    """Show current status of a swarm run."""
    run_path = Path(state_dir)
    if not (run_path / "swarm_state.json").is_file():
        print_error(f"No swarm state found for {run_id}")
        raise typer.Exit(1)

    from aec_bench.evolution.swarm.resume import load_resumed_state

    try:
        state = load_resumed_state(run_path)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc
    if state.run_id != run_id:
        print_error(f"Swarm state run ID is {state.run_id!r}, not {run_id!r}")
        raise typer.Exit(1)
    console.print(f"[bold]Run:[/bold] {state.run_id}")
    console.print(f"  Evals: {state.total_evals}")
    console.print(f"  Best score: {state.best_score:.2f}")
    console.print(f"  Cost: ${state.total_cost_usd:.2f}")


@app.command("history")
def swarm_history(
    state_dir: str = typer.Option(".", "--state-dir", help="Directory containing swarm runs"),
) -> None:
    """List past swarm runs."""
    state_path = Path(state_dir)
    runs: list[dict[str, Any]] = []
    for run_path in sorted(path for path in state_path.glob("**/swarm_state.json") if path.is_file()):
        try:
            from aec_bench.evolution.swarm.resume import load_resumed_state

            state = load_resumed_state(run_path.parent)
        except ValueError:
            continue
        if state.run_id:
            runs.append(
                {
                    "run_id": state.run_id,
                    "evals": state.total_evals,
                    "best_score": state.best_score,
                    "cost_usd": state.total_cost_usd,
                }
            )

    if not runs:
        console.print("[dim]No swarm runs found.[/dim]")
    else:
        for run in runs:
            console.print(
                f"  {run['run_id']} — {run['evals']} evals, best {run['best_score']:.2f}, ${run['cost_usd']:.2f}"
            )
