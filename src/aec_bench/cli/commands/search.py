# ABOUTME: CLI search command for finding task templates and seeds.
# ABOUTME: Supports full-text search across descriptions, tags, standards, inputs, and outputs.

# ruff: noqa: B008

import time
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table
from rich.text import Text

from aec_bench.cli.output import console, emit
from aec_bench.config import load_config
from aec_bench.search import build_index_from_paths, search

_TEMPLATES_ROOT = Path(__file__).resolve().parents[2] / "templates" / "builtin"


def search_command(
    query: Annotated[str, typer.Argument(help="Search terms (space-separated, AND logic)")],
    discipline: Annotated[str | None, typer.Option("--discipline", "-d", help="Filter by discipline")] = None,
    templates_only: Annotated[bool, typer.Option("--templates-only", "-t", help="Only show templates")] = False,
    seeds_only: Annotated[bool, typer.Option("--seeds-only", "-s", help="Only show seeds")] = False,
) -> None:
    """Search task templates and seeds by keyword.

    Searches across: name, description, tags, standards, inputs, and outputs.
    Multiple terms use AND logic -- all terms must match.

    Returns: list of matches, each with name, kind, discipline, category,
    description, long_description, tags, standards, has_template.

    Examples:
      aec-bench search "voltage drop" --discipline electrical
      aec-bench search "cable sizing" --json | jq '.data[].name'
    """
    start = time.monotonic()
    config = load_config()
    tasks_root = config.project_root / config.tasks_root if config.project_root else Path("tasks")
    templates_root = _TEMPLATES_ROOT

    index = build_index_from_paths(tasks_root, templates_root)

    kind_filter = None
    if templates_only:
        kind_filter = "template"
    elif seeds_only:
        kind_filter = "seed"

    results = search(query, index, discipline=discipline, kind=kind_filter)

    data = [
        {
            "name": r.name,
            "kind": r.kind,
            "discipline": r.discipline,
            "category": r.category,
            "description": r.description,
            "long_description": r.long_description,
            "tags": list(r.tags),
            "standards": list(r.standards),
            "has_template": r.has_template,
        }
        for r in results
    ]

    def _render(d: list) -> None:
        if not d:
            console.print(f"[dim]No results for [bold]{query}[/bold][/dim]")
            return

        # Summary line
        template_count = sum(1 for r in d if r["kind"] == "template")
        seed_count = sum(1 for r in d if r["kind"] == "seed")
        console.print(
            f"\n[bold]{len(d)}[/bold] results for [bold cyan]{query}[/bold cyan]"
            f"  ({template_count} templates, {seed_count} seeds)\n"
        )

        # Results table
        table = Table(show_header=True, header_style="bold", expand=True, pad_edge=False)
        table.add_column("Name", style="bold", no_wrap=True, ratio=2)
        table.add_column("Kind", no_wrap=True, ratio=1)
        table.add_column("Discipline", no_wrap=True, ratio=1)
        table.add_column("Category", no_wrap=True, ratio=1)
        table.add_column("Description", ratio=4)

        for entry in d:
            kind_style = "green" if entry["kind"] == "template" else "dim"
            kind_marker = "\u25c6" if entry["kind"] == "template" else "\u00b7"
            desc = entry["long_description"] if entry["long_description"] else entry["description"]
            # Truncate long descriptions
            if len(desc) > 80:
                desc = desc[:77] + "..."
            table.add_row(
                entry["name"],
                Text(f"{kind_marker} {entry['kind']}", style=kind_style),
                entry["discipline"],
                entry["category"],
                desc,
            )

        console.print(table)
        console.print()

    emit("search", data, start_time=start, human_renderer=_render)
