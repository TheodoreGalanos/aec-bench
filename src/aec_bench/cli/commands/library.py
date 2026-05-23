# ABOUTME: CLI driver for `aec-bench library export` — emits the library catalogue JSON artefact.
# ABOUTME: Thin wrapper around tasks.library_export.build_catalogue with flag plumbing.

from __future__ import annotations

import json
import time
from pathlib import Path

import click
import typer

from aec_bench import __version__
from aec_bench.cli.output import emit, print_error, print_success
from aec_bench.tasks.library_export import _git_short_sha, build_catalogue

app = typer.Typer(
    help="Library catalogue export for external consumers (e.g. the aec-bench site).",
    no_args_is_help=True,
)

_DEFAULT_TEMPLATES_ROOT = Path("src/aec_bench/templates/builtin")


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
            library_version=__version__,
            library_commit=_git_short_sha(cwd=Path.cwd()),
        )
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc

    payload = catalogue.model_dump(mode="json")
    serialised = json.dumps(payload, indent=2 if pretty else None, default=str)

    if stdout:
        typer.echo(serialised)
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(serialised, encoding="utf-8")

    summary_data = {
        "out_path": str(out),
        "total_templates": catalogue.counts.total_templates,
        "total_seeds": catalogue.counts.total_seeds,
        "skipped_seeds": len(diagnostics.skipped_seeds),
        "disciplines": sorted(catalogue.counts.by_discipline.keys()),
    }

    def _human(data: dict) -> None:
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
