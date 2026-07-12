# ABOUTME: CLI commands for listing, materializing, running, and verifying hydraulic worlds.
# ABOUTME: Exposes the same model-independent APIs that PR19 can later wrap as bounded actions.

from __future__ import annotations

import time
from pathlib import Path

import typer

from aec_bench.cli.output import emit
from aec_bench.task_world_templates.hydraulics import (
    build_hydraulic_run_request,
    execute_hydraulic_world,
    materialize_hydraulic_world,
    verify_hydraulic_world,
)
from aec_bench.task_world_templates.hydraulics.registry import list_hydraulic_world_ids

app = typer.Typer(help="Run deterministic public hydraulic mini-worlds.")


@app.command("list")
def list_command() -> None:
    """List public hydraulic worlds without exposing model action tools."""
    start = time.monotonic()
    world_ids = list_hydraulic_world_ids()
    emit(
        "task hydraulic-world list",
        {"count": len(world_ids), "world_ids": list(world_ids)},
        start_time=start,
    )


@app.command("materialize")
def materialize_command(
    world_id: str = typer.Argument(..., help="Registered public hydraulic world id"),
    output: Path = typer.Option(..., "--output", "-o", help="Immutable source package directory"),
) -> None:
    """Materialize exact source and engine identities for one public world."""
    start = time.monotonic()
    try:
        package = materialize_hydraulic_world(world_id, output)
    except (KeyError, ValueError) as exc:
        emit("task hydraulic-world materialize", None, errors=[str(exc)], start_time=start)
        return
    emit(
        "task hydraulic-world materialize",
        {"world_id": world_id, "package_dir": str(package)},
        start_time=start,
    )


@app.command("run")
def run_command(
    package_dir: Path = typer.Argument(..., help="Materialized immutable hydraulic package"),
    scenario: str = typer.Option(..., "--scenario", help="Declared scenario id"),
    output: Path = typer.Option(..., "--output", "-o", help="Immutable run directory outside the package"),
) -> None:
    """Execute one source-bound deterministic hydraulic scenario."""
    start = time.monotonic()
    try:
        request = build_hydraulic_run_request(package_dir, scenario_id=scenario)
        run = execute_hydraulic_world(package_dir, output, request)
    except (OSError, ValueError) as exc:
        emit("task hydraulic-world run", None, errors=[str(exc)], start_time=start)
        return
    emit(
        "task hydraulic-world run",
        {
            "world_id": request.world_id,
            "scenario_id": request.scenario_id,
            "run_id": request.run_id,
            "run_dir": str(run),
        },
        start_time=start,
    )


@app.command("verify")
def verify_command(
    package_dir: Path = typer.Argument(..., help="Materialized immutable hydraulic package"),
    run_dir: Path = typer.Argument(..., help="Completed immutable hydraulic run"),
) -> None:
    """Verify package, run, report, calculations, and source-owned criteria."""
    start = time.monotonic()
    try:
        verification = verify_hydraulic_world(package_dir, run_dir)
    except (OSError, ValueError) as exc:
        emit("task hydraulic-world verify", None, errors=[str(exc)], start_time=start)
        return
    emit(
        "task hydraulic-world verify",
        verification.model_dump(mode="json"),
        start_time=start,
    )
