# ABOUTME: Full-text search index for task templates and seeds.
# ABOUTME: Shared by CLI search command and TUI library search bar.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from aec_bench.generation.discovery import (
    LibrarySeed,
    LibraryTemplate,
    scan_seeds,
    scan_templates,
)


@dataclass(frozen=True)
class SearchEntry:
    """A searchable item in the task library."""

    name: str
    discipline: str
    category: str
    description: str
    long_description: str
    tags: tuple[str, ...]
    standards: tuple[str, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    kind: Literal["seed", "template"]
    has_template: bool
    path: Path
    # Pre-built lowercase search text for matching
    _search_text: str


def _entry_from_seed(seed: LibrarySeed, *, has_template: bool) -> SearchEntry:
    """Build a SearchEntry from a LibrarySeed."""
    search_parts = [
        seed.task_id,
        seed.task_name,
        seed.description,
        seed.discipline,
        seed.category,
        seed.complexity,
        *seed.standards,
        *seed.inputs,
        *seed.outputs,
    ]
    return SearchEntry(
        name=seed.task_id,
        discipline=seed.discipline,
        category=seed.category,
        description=seed.description,
        long_description="",
        tags=(),
        standards=seed.standards,
        inputs=seed.inputs,
        outputs=seed.outputs,
        kind="seed",
        has_template=has_template,
        path=seed.path,
        _search_text=" ".join(search_parts).lower(),
    )


def _entry_from_template(template: LibraryTemplate) -> SearchEntry:
    """Build a SearchEntry from a LibraryTemplate."""
    meta = template.params_raw.get("meta", {})
    params = template.params_raw.get("params", {})
    outputs = template.params_raw.get("outputs", {})

    description = meta.get("description", "")
    long_description = meta.get("long_description", "")
    tags = tuple(meta.get("tags", []))
    standards = tuple(meta.get("standards", []))

    input_descs = tuple(spec.get("description", name) for name, spec in params.items())
    output_descs = tuple(spec.get("description", name) for name, spec in outputs.items())

    search_parts = [
        template.task_id,
        description,
        long_description,
        template.discipline,
        meta.get("category", ""),
        *tags,
        *standards,
        *input_descs,
        *output_descs,
    ]
    return SearchEntry(
        name=template.task_id,
        discipline=template.discipline,
        category=meta.get("category", ""),
        description=description,
        long_description=long_description,
        tags=tags,
        standards=standards,
        inputs=input_descs,
        outputs=output_descs,
        kind="template",
        has_template=True,
        path=template.path,
        _search_text=" ".join(search_parts).lower(),
    )


def build_index(
    seeds: list[LibrarySeed],
    templates: list[LibraryTemplate],
) -> list[SearchEntry]:
    """Build a search index from scanned seeds and templates."""
    template_ids = {(t.discipline, t.task_id) for t in templates}
    entries: list[SearchEntry] = []

    # Add template entries (these take priority over seeds with same ID)
    template_task_ids: set[tuple[str, str]] = set()
    for template in templates:
        entries.append(_entry_from_template(template))
        template_task_ids.add((template.discipline, template.task_id))

    # Add seed entries for tasks that don't have a template
    for seed in seeds:
        has_template = (seed.discipline, seed.task_id) in template_ids
        if (seed.discipline, seed.task_id) not in template_task_ids:
            entries.append(_entry_from_seed(seed, has_template=has_template))

    return sorted(entries, key=lambda e: (e.discipline, e.category, e.name))


def build_index_from_paths(
    tasks_root: Path,
    templates_root: Path,
) -> list[SearchEntry]:
    """Build a search index by scanning filesystem paths."""
    seeds = scan_seeds(tasks_root)
    templates = scan_templates(templates_root)
    return build_index(seeds, templates)


def search(
    query: str,
    index: list[SearchEntry],
    *,
    discipline: str | None = None,
    kind: Literal["seed", "template"] | None = None,
) -> list[SearchEntry]:
    """Search the index for entries matching the query.

    All query terms must appear in the entry's search text (AND logic).
    Results are returned in relevance order (more term hits = higher rank).
    """
    if not query.strip():
        results = list(index)
    else:
        terms = query.lower().split()
        results = [entry for entry in index if all(term in entry._search_text for term in terms)]

    if discipline:
        results = [e for e in results if e.discipline == discipline]

    if kind:
        results = [e for e in results if e.kind == kind]

    return results
