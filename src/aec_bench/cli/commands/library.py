# ABOUTME: CLI driver for `aec-bench library export` — emits the library catalogue JSON artefact.
# ABOUTME: Thin wrapper around tasks.library_export.build_catalogue with flag plumbing.

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import click
import typer

from aec_bench.cli.output import emit, print_error, print_success
from aec_bench.tasks.library_export import build_catalogue, catalogue_json_bytes

app = typer.Typer(
    help="Library catalogue export for external consumers (e.g. the aec-bench site).",
    no_args_is_help=True,
)

_DEFAULT_TEMPLATES_ROOT = Path(__file__).resolve().parents[2] / "templates" / "builtin"


@app.callback()
def _callback() -> None:
    """Library catalogue management commands."""


_DEFAULT_TASKS_ROOT = Path("tasks")
_DEFAULT_OUT_PATH = Path("artefacts/library-catalogue.json")


@app.command("export")
def export_cmd(
    ctx: typer.Context,
    out: Path = typer.Option(_DEFAULT_OUT_PATH, "--out", help="Output file path (ignored if --stdout is given)."),
    stdout: bool = typer.Option(False, "--stdout", help="Write the catalogue JSON to stdout instead of a file."),
    pretty: bool = typer.Option(False, "--pretty", help="Indent the JSON output with 2 spaces (default: compact)."),
    json_envelope: bool = typer.Option(False, "--json", help="Emit CLIResult envelope on stdout (file still written)."),
    templates_root: Path = typer.Option(
        _DEFAULT_TEMPLATES_ROOT,
        "--templates-root",
        help="Override templates directory.",
    ),
    tasks_root: Path = typer.Option(
        _DEFAULT_TASKS_ROOT,
        "--tasks-root",
        help="Override tasks directory (seeds live here).",
    ),
) -> None:
    """Export the library catalogue (templates + seeds) as a versioned JSON artefact."""
    # Mutex check: only error when the user actually passed --out on the CLI alongside --stdout.
    # We use Click's parameter source so the default value doesn't spuriously trip the check.
    out_was_explicit = ctx.get_parameter_source("out") == click.core.ParameterSource.COMMANDLINE
    if stdout and out_was_explicit:
        print_error("--out and --stdout are mutually exclusive")
        raise typer.Exit(1)

    start = time.monotonic()

    try:
        catalogue, diagnostics = build_catalogue(
            templates_root=templates_root,
            tasks_root=tasks_root,
        )
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc

    payload = catalogue_json_bytes(catalogue, pretty=pretty)

    if stdout:
        typer.echo(payload.decode("utf-8"), nl=False)
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)

    disciplines = sorted({entry.discipline for entry in [*catalogue.templates, *catalogue.seeds]})

    summary_data = {
        "out_path": str(out),
        "total_templates": len(catalogue.templates),
        "total_seeds": len(catalogue.seeds),
        "skipped_seeds": len(diagnostics.skipped_seeds),
        "disciplines": disciplines,
    }

    def _human(data: dict[str, Any]) -> None:
        skipped = data["skipped_seeds"]
        skipped_note = f" ({skipped} skipped)" if skipped else ""
        print_success(
            f"Wrote {data['out_path']} — {data['total_templates']} templates, "
            f"{data['total_seeds']} seeds{skipped_note}, "
            f"{len(data['disciplines'])} disciplines"
        )

    if json_envelope:
        emit("library export", summary_data, start_time=start)
    else:
        _human(summary_data)
