# ABOUTME: CLI commands for composite task-world templates.
# ABOUTME: Lists template specs and materialises or verifies compiled example packages.

from __future__ import annotations

import json
import time
from pathlib import Path

import typer

from aec_bench.cli.output import emit, print_table
from aec_bench.task_world_templates.catalogue import get_template, list_templates
from aec_bench.task_world_templates.lifecycles import lifecycle_variant_ids
from aec_bench.task_world_templates.materializer import (
    materialize_template_example,
    materialize_template_lifecycle,
    verify_template_example,
    verify_template_lifecycle,
)

app = typer.Typer(help="Inspect composite task-world templates.")


@app.command("list")
def list_command() -> None:
    start = time.monotonic()
    templates = list_templates()
    data = {
        "count": len(templates),
        "templates": [
            {
                "template_id": template.template_id,
                "name": template.name,
                "pattern": template.pattern,
                "disciplines": template.discipline_scope,
                "stage_count": len(template.stages),
                "handoff_count": len(template.handoffs),
                "data_gap_count": len(template.data_gaps),
            }
            for template in templates
        ],
    }
    emit("task composite-template list", data, start_time=start, human_renderer=_render_templates)


@app.command("materialize-example")
def materialize_example_command(
    template_id: str = typer.Argument(..., help="Composite task-world template id"),
    output: Path = typer.Option(..., "--output", "-o", help="Directory where the example package is written"),
) -> None:
    start = time.monotonic()
    try:
        template = get_template(template_id)
    except KeyError as exc:
        emit("task composite-template materialize-example", None, errors=[str(exc)], start_time=start)
        return

    package_dir = materialize_template_example(template, output)
    result = verify_template_example(package_dir)
    emit(
        "task composite-template materialize-example",
        {
            "template_id": template.template_id,
            "package_dir": str(package_dir),
            "overall": result["overall"],
            "score": result["score"],
            "data_gap_count": len(result["data_gaps"]),
        },
        start_time=start,
    )


@app.command("verify-example")
def verify_example_command(
    package_dir: Path = typer.Argument(..., help="Materialized composite task-world package directory"),
) -> None:
    start = time.monotonic()
    result = verify_template_example(package_dir)
    emit("task composite-template verify-example", result, start_time=start)


@app.command("materialize-lifecycle")
def materialize_lifecycle_command(
    template_id: str = typer.Argument(..., help="Composite task-world template id"),
    output: Path = typer.Option(..., "--output", "-o", help="Directory where the lifecycle package is written"),
    variant: str | None = typer.Option(None, "--variant", help="Registered semantic lifecycle variant id"),
) -> None:
    """Materialize a registered staged evidence-lifecycle package."""
    start = time.monotonic()
    try:
        template = get_template(template_id)
        package_dir = materialize_template_lifecycle(template, output, variant_id=variant)
    except (KeyError, ValueError) as exc:
        emit("task composite-template materialize-lifecycle", None, errors=[str(exc)], start_time=start)
        return
    assert template.evidence_lifecycle is not None
    emit(
        "task composite-template materialize-lifecycle",
        {
            "template_id": template.template_id,
            "package_dir": str(package_dir),
            "checkpoint_count": len(template.evidence_lifecycle.checkpoints),
            "variant_id": _materialized_variant_id(package_dir),
        },
        start_time=start,
    )


@app.command("list-lifecycle-variants")
def list_lifecycle_variants_command(
    template_id: str = typer.Argument(..., help="Composite task-world template id"),
) -> None:
    """List public semantic variants registered for one lifecycle template."""
    start = time.monotonic()
    try:
        variants = lifecycle_variant_ids(template_id)
    except KeyError as exc:
        emit("task composite-template list-lifecycle-variants", None, errors=[str(exc)], start_time=start)
        return
    emit(
        "task composite-template list-lifecycle-variants",
        {"template_id": template_id, "variants": list(variants)},
        start_time=start,
    )


@app.command("verify-lifecycle")
def verify_lifecycle_command(
    package_dir: Path = typer.Argument(..., help="Materialized lifecycle package directory"),
    run_dir: Path = typer.Option(..., "--run-dir", help="Completed lifecycle run directory"),
) -> None:
    """Verify one completed evidence-lifecycle run."""
    start = time.monotonic()
    result = verify_template_lifecycle(package_dir, run_dir)
    emit("task composite-template verify-lifecycle", result, start_time=start)


def _materialized_variant_id(package_dir: Path) -> str | None:
    path = package_dir / "hidden" / "variant.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload["variant_id"])


def _render_templates(data: dict[str, object]) -> None:
    templates = data["templates"]
    if not isinstance(templates, list):
        return
    rows = [
        [
            str(template["template_id"]),
            str(template["name"]),
            ", ".join(template["disciplines"]),
            str(template["stage_count"]),
            str(template["handoff_count"]),
        ]
        for template in templates
        if isinstance(template, dict)
    ]
    print_table(
        "Composite Task-World Templates",
        ["Template", "Name", "Disciplines", "Stages", "Handoffs"],
        rows,
    )
