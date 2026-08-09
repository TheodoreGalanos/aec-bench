# ABOUTME: CLI commands for current staged evidence-lifecycle tasks.
# ABOUTME: Materializes, inspects, runs, and verifies the three task-owned definitions.

from __future__ import annotations

import json
import time
from pathlib import Path

import typer

from aec_bench.cli.output import emit, print_table
from aec_bench.lifecycles.catalogue import (
    lifecycle_definition,
    lifecycle_operation_resolver,
    lifecycle_smoke_environment,
    lifecycle_template_ids,
    lifecycle_variant_ids,
    materialize_lifecycle,
    verify_lifecycle,
)
from aec_bench.lifecycles.runtime.lifecycle import run_evidence_lifecycle
from aec_bench.lifecycles.runtime.request_protocol import EvidenceLifecycleError

app = typer.Typer(help="Inspect and run staged evidence-lifecycle tasks.")


@app.command("list")
def list_command() -> None:
    start = time.monotonic()
    definitions = [lifecycle_definition(template_id) for template_id in sorted(lifecycle_template_ids())]
    data = {
        "count": len(definitions),
        "lifecycles": [
            {
                **definition.metadata.model_dump(mode="json"),
                "lifecycle_id": definition.lifecycle.lifecycle_id,
                "checkpoint_count": len(definition.lifecycle.checkpoints),
            }
            for definition in definitions
        ],
    }
    emit("task lifecycle list", data, start_time=start, human_renderer=_render_lifecycles)


@app.command("materialize")
def materialize_command(
    template_id: str = typer.Argument(..., help="Lifecycle task id"),
    output: Path = typer.Option(..., "--output", "-o", help="Directory where the lifecycle package is written"),
    variant: str | None = typer.Option(None, "--variant", help="Public semantic lifecycle variant id"),
) -> None:
    start = time.monotonic()
    try:
        definition = lifecycle_definition(template_id)
        package_dir = materialize_lifecycle(template_id, output, variant_id=variant)
    except (KeyError, ValueError) as exc:
        emit("task lifecycle materialize", None, errors=[str(exc)], start_time=start)
        return
    emit(
        "task lifecycle materialize",
        {
            "template_id": template_id,
            "package_dir": str(package_dir),
            "checkpoint_count": len(definition.lifecycle.checkpoints),
            "variant_id": _materialized_variant_id(package_dir),
        },
        start_time=start,
    )


@app.command("list-variants")
def list_variants_command(template_id: str = typer.Argument(..., help="Lifecycle task id")) -> None:
    start = time.monotonic()
    try:
        variants = lifecycle_variant_ids(template_id)
    except KeyError as exc:
        emit("task lifecycle list-variants", None, errors=[str(exc)], start_time=start)
        return
    emit(
        "task lifecycle list-variants",
        {"template_id": template_id, "variants": list(variants)},
        start_time=start,
    )


@app.command("verify")
def verify_command(
    package_dir: Path = typer.Argument(..., help="Materialized lifecycle package directory"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Completed lifecycle run directory"),
) -> None:
    start = time.monotonic()
    emit("task lifecycle verify", verify_lifecycle(package_dir, run_dir), start_time=start)


@app.command("run-smoke")
def run_smoke_command(
    package_dir: Path = typer.Argument(..., help="Materialized public lifecycle package directory"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Empty output directory for the deterministic run"),
) -> None:
    start = time.monotonic()
    try:
        template_id = _package_template_id(package_dir)
        environment = lifecycle_smoke_environment(template_id, package_dir)
        if environment is None:
            raise ValueError(f"lifecycle task {template_id!r} does not declare a smoke environment")
        lifecycle = run_evidence_lifecycle(
            package_dir,
            run_dir,
            episode_environment=environment,
            operation_resolver=lifecycle_operation_resolver(package_dir, run_dir),
        )
        verification = verify_lifecycle(package_dir, run_dir)
    except (EvidenceLifecycleError, json.JSONDecodeError, KeyError, OSError, ValueError) as exc:
        emit("task lifecycle run-smoke", None, errors=[str(exc)], start_time=start)
        return
    emit(
        "task lifecycle run-smoke",
        {
            "template_id": template_id,
            "package_dir": str(package_dir),
            "run_dir": str(run_dir),
            "lifecycle_status": lifecycle["status"],
            "overall": verification["overall"],
            "passed": verification["passed"],
            "reward": verification["reward"],
            "gates": verification["gates"],
        },
        start_time=start,
    )


def _materialized_variant_id(package_dir: Path) -> str | None:
    path = package_dir / "hidden" / "variant.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["variant_id"])


def _package_template_id(package_dir: Path) -> str:
    payload = json.loads((Path(package_dir) / "template.json").read_text(encoding="utf-8"))
    template_id = payload.get("template_id") if isinstance(payload, dict) else None
    if not isinstance(template_id, str) or not template_id:
        raise ValueError("lifecycle package template identity is invalid")
    return template_id


def _render_lifecycles(data: dict[str, object]) -> None:
    lifecycles = data["lifecycles"]
    if not isinstance(lifecycles, list):
        return
    rows = [
        [
            str(lifecycle["template_id"]),
            str(lifecycle["name"]),
            str(lifecycle["discipline"]),
            str(lifecycle["checkpoint_count"]),
        ]
        for lifecycle in lifecycles
        if isinstance(lifecycle, dict)
    ]
    print_table("Lifecycle Tasks", ["Task", "Name", "Discipline", "Checkpoints"], rows)
