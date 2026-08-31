# ABOUTME: Provides CLI commands for building and checking generated catalogues.
# ABOUTME: Exposes semantic catalogue differences without changing runtime lookup APIs.

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import typer

from aec_bench.catalogue import build_catalogues, check_catalogues, diff_catalogue
from aec_bench.cli.output import emit, print_error, print_success

app = typer.Typer(
    help="Build, check, and compare generated world and lifecycle catalogues.",
    no_args_is_help=True,
)

_DEFAULT_ROOT = Path(__file__).resolve().parents[4]


@app.callback()
def _callback() -> None:
    """Manage generated world and lifecycle catalogues."""


def _render_summary(data: dict[str, Any]) -> None:
    print_success(
        f"{data['status'].capitalize()} catalogues — "
        f"{data['worlds']} worlds, {data['profiles']} profiles, "
        f"{data['lifecycles']} lifecycles, {data['variants']} variants"
    )


@app.command("build")
def build_cmd(
    root: Path = typer.Option(_DEFAULT_ROOT, "--root", help="Repository root containing src/aec_bench."),
    snapshot: Path | None = typer.Option(
        None,
        "--snapshot",
        help="Also write a semantic JSON snapshot for later catalogue diff.",
    ),
) -> None:
    """Generate both committed Python catalogues."""

    start = time.monotonic()
    try:
        data = build_catalogues(root, snapshot)
    except (ValueError, OSError) as error:
        print_error(str(error))
        raise typer.Exit(1) from error
    emit("catalogue build", data, start_time=start, human_renderer=_render_summary)


@app.command("check")
def check_cmd(
    root: Path = typer.Option(_DEFAULT_ROOT, "--root", help="Repository root containing src/aec_bench."),
) -> None:
    """Check generated freshness, semantic validity, and stable ordering."""

    start = time.monotonic()
    try:
        data = check_catalogues(root)
    except (ValueError, OSError) as error:
        print_error(str(error))
        raise typer.Exit(1) from error
    emit("catalogue check", data, start_time=start, human_renderer=_render_summary)


def _render_diff(data: dict[str, Any]) -> None:
    added = data["added"]
    changed = data["changed"]
    removed = data["removed"]
    print_success(f"Catalogue diff against {data['against']}")
    for label, entries in (("Added", added), ("Changed", changed), ("Removed", removed)):
        typer.echo(f"{label}: {len(entries)}")
        for entry in entries:
            name = f"{entry['kind']} {entry.get('key', entry['id'])}"
            if label == "Changed":
                typer.echo(f"  {name}")
                for field, change in sorted(entry["fields"].items()):
                    typer.echo(f"    {field}: {change['before']} -> {change['after']}")
            else:
                typer.echo(f"  {name}")


@app.command("diff")
def diff_cmd(
    against: str = typer.Option(..., "--against", help="Path to a JSON semantic catalogue snapshot."),
) -> None:
    """Show added, changed, and removed semantic catalogue entries."""

    start = time.monotonic()
    try:
        data = diff_catalogue(against)
    except (ValueError, OSError) as error:
        print_error(str(error))
        raise typer.Exit(1) from error
    emit("catalogue diff", data, start_time=start, human_renderer=_render_diff)
