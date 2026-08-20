# ABOUTME: CLI discovery and direct-run commands for registered Interactive Worlds.
# ABOUTME: Calls the public world facade and complete Python trial functions without task semantics.

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any

import typer

from aec_bench import worlds
from aec_bench.cli.commands.pump_station_world import app as pump_station_app
from aec_bench.cli.output import emit
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.trials import plan_trials

app = typer.Typer(help="Discover and run registered Interactive Worlds.")
app.add_typer(pump_station_app, name="pump-station")


def _info(value: worlds.WorldInfo) -> dict[str, Any]:
    payload = asdict(value)
    capabilities = payload.get("capabilities")
    if isinstance(capabilities, frozenset):
        payload["capabilities"] = sorted(capabilities)
    return payload


@app.command("list")
def list_worlds() -> None:
    """List registered Interactive Worlds."""

    start = time.monotonic()
    emit("task world list", [_info(value) for value in worlds.list()], start_time=start)


@app.command("find")
def find_worlds(query: str = typer.Argument(help="Text to match")) -> None:
    """Find registered Interactive Worlds."""

    start = time.monotonic()
    emit("task world find", [_info(value) for value in worlds.find(query)], start_time=start)


@app.command("show")
def show_world(world_id: str = typer.Argument(help="Registered world ID")) -> None:
    """Show one registered Interactive World."""

    start = time.monotonic()
    try:
        value = worlds.get(world_id)
    except KeyError as error:
        emit("task world show", None, errors=[str(error)], start_time=start)
        raise typer.Exit(1) from error
    emit("task world show", _info(value), start_time=start)


@app.command("profiles")
def list_profiles(world_id: str = typer.Argument(help="Registered world ID")) -> None:
    """List the registered profiles for one world."""

    start = time.monotonic()
    try:
        values = worlds.profiles(world_id)
    except KeyError as error:
        emit("task world profiles", None, errors=[str(error)], start_time=start)
        raise typer.Exit(1) from error
    emit("task world profiles", [asdict(value) for value in values], start_time=start)


@app.command("run")
def run_world(
    world_id: str = typer.Argument(help="Registered world ID"),
    profile: str = typer.Option(..., "--profile", help="Registered profile ID"),
    instruction: str = typer.Option(..., "--instruction", help="Actor objective"),
    model: str = typer.Option(..., "--model", help="Provider model"),
    adapter: str = typer.Option("prime-agent", "--adapter", help="Supported provider adapter"),
    repetitions: int = typer.Option(1, "--repetitions", "-n", min=1),
    work_root: Path = typer.Option(Path("artefacts/world-runs"), "--work-root"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Plan and run one registered Interactive World task."""

    from aec_bench.harness.world_routing import run_selected_world, validate_world_routes
    from aec_bench.harness.world_trials import run_world_experiment

    start = time.monotonic()
    try:
        selected = worlds.task(world_id, profile=profile, instruction=instruction)
        agent = AgentConfig(
            name=f"{adapter}-{model}",
            adapter=adapter,
            model=model,
            parameters={
                "isolation": "macos-seatbelt",
                "max_sessions": 8,
                "max_host_controls": 8,
                "max_world_actions": 64,
                "max_model_calls": 32,
                "max_tokens": 100_000,
                "max_cost_usd": str(Decimal("25")),
                "max_wall_seconds": 1800,
            },
        )
        trials = plan_trials(
            f"world-{world_id}",
            tasks=[selected],
            agents=[agent],
            compute=ComputeConfig(backend="local"),
            repetitions=repetitions,
        )
        validate_world_routes([selected], trials)
    except (KeyError, ValueError) as error:
        emit("task world run", None, errors=[str(error)], start_time=start)
        raise typer.Exit(1) from error
    if dry_run:
        emit(
            "task world run",
            {
                "task": {"task_id": selected.task_id},
                "trials": [trial.trial_id for trial in trials],
            },
            start_time=start,
        )
        return
    records = asyncio.run(
        run_world_experiment(
            tasks=[selected],
            trials=trials,
            run_trial=partial(run_selected_world, work_root=work_root),
        )
    )
    emit("task world run", [record.model_dump(mode="json") for record in records], start_time=start)


__all__ = ("app",)
