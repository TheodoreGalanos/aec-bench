# ABOUTME: Full-text search index for task templates and seeds.
# ABOUTME: Shared by CLI search command and TUI library search bar.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from aec_bench.tasks.library_export import LoadedSeed, load_seeds
from aec_bench.templates.registry import LoadedTemplate, discover_templates


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


def _entry_from_seed(seed: LoadedSeed, *, has_template: bool) -> SearchEntry:
    """Build a SearchEntry from a validated seed."""
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


def _entry_from_template(template: LoadedTemplate) -> SearchEntry:
    """Build a SearchEntry from a validated template."""
    config = template.config
    meta = config.meta
    description = meta.description
    long_description = meta.long_description
    tags = tuple(meta.tags)
    standards = tuple(meta.standards)
    input_descs = tuple(spec.description or name for name, spec in config.params.items())
    output_descs = tuple(spec.description or name for name, spec in config.outputs.items())

    search_parts = [
        meta.name,
        description,
        long_description,
        meta.discipline,
        meta.category,
        *tags,
        *standards,
        *input_descs,
        *output_descs,
    ]
    return SearchEntry(
        name=meta.name,
        discipline=meta.discipline,
        category=meta.category,
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
    seeds: list[LoadedSeed],
    templates: list[LoadedTemplate],
) -> list[SearchEntry]:
    """Build a search index from scanned seeds and templates."""
    template_ids = {(t.config.meta.discipline, t.config.meta.name) for t in templates}
    entries: list[SearchEntry] = []

    # Add template entries (these take priority over seeds with same ID)
    template_task_ids: set[tuple[str, str]] = set()
    for template in templates:
        entries.append(_entry_from_template(template))
        template_task_ids.add((template.config.meta.discipline, template.config.meta.name))

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
    seeds, _seed_diagnostics = load_seeds(tasks_root)
    templates, _template_diagnostics = discover_templates(user_dirs=[templates_root], include_builtin=False)
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
