# ABOUTME: Builds the public library catalogue from template and seed source.
# ABOUTME: Projection layer — reads templates via registry, loads seeds, validates.

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from aec_bench.contracts.library_catalogue import (
    CatalogueCounts,
    InputField,
    LibraryCatalogue,
    OutputField,
    SeedEntry,
    TemplateEntry,
)
from aec_bench.contracts.seed_task import SeedTask, StructuredSeedField
from aec_bench.templates.contracts import ParamSpec, TemplateConfig
from aec_bench.templates.registry import load_template


@dataclass(frozen=True)
class SkippedEntry:
    """Diagnostic record for a template or seed that was skipped during export."""

    path: Path
    reason: str
    kind: Literal["template", "seed"]


@dataclass(frozen=True)
class ExportDiagnostics:
    """Non-fatal skip counts surfaced by the CLI but not serialised into the artefact."""

    skipped_templates: list[SkippedEntry]
    skipped_seeds: list[SkippedEntry]


class DuplicateTemplateError(ValueError):
    """Raised when two templates share (discipline, task_id)."""


# Canonical ordering for difficulty tier names so exported arrays match intuition
# (easy → medium → hard) rather than alphabetical ("easy" < "hard" < "medium").
# Unknown tier names sort after the canonical set, alphabetically among themselves.
_DIFFICULTY_ORDER: dict[str, int] = {"easy": 0, "medium": 1, "hard": 2}


def _sort_difficulty_tiers(tiers: list[str]) -> list[str]:
    """Return tier names in canonical order, unknowns appended alphabetically."""
    return sorted(tiers, key=lambda t: (_DIFFICULTY_ORDER.get(t, 99), t))


def _slug_to_title(slug: str) -> str:
    """Turn a slug identifier into a human-readable title (e.g. 'voltage-drop' → 'Voltage Drop').

    Lossy for acronyms (e.g. 'bess-sizing' → 'Bess Sizing'); templates that care about
    acronym capitalisation should gain a proper task_name in their params.toml meta
    block and this projection should then read it instead of deriving.
    """
    return slug.replace("-", " ").replace("_", " ").title()


def load_seeds(tasks_root: Path) -> tuple[list[SeedTask], list[SkippedEntry]]:
    """Walk tasks_root for source_task.json files and validate each against SeedTask.

    Returns (valid_seeds, skipped_entries). Malformed or schema-violating files
    land in skipped_entries with a reason string — they never fail the scan.
    """
    if not tasks_root.is_dir():
        return [], []

    valid: list[SeedTask] = []
    skipped: list[SkippedEntry] = []

    for path in sorted(tasks_root.rglob("source_task.json")):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            skipped.append(SkippedEntry(path=path, reason=f"read error: {exc}", kind="seed"))
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            skipped.append(SkippedEntry(path=path, reason=f"json decode error: {exc}", kind="seed"))
            continue

        try:
            seed = SeedTask.model_validate(data)
        except ValidationError as exc:
            skipped.append(
                SkippedEntry(
                    path=path,
                    reason=f"schema validation failed: {exc.errors()[0]['msg']}",
                    kind="seed",
                )
            )
            continue

        valid.append(seed)

    return valid, skipped


def _param_to_input(name: str, spec: ParamSpec) -> InputField:
    """Map a single ParamSpec to a public InputField."""
    return InputField(
        name=name,
        description=spec.description,
        unit=spec.unit,
        type=spec.type.value,  # type: ignore[arg-type]  — ParamType literal matches InputField type
    )


def _project_template(cfg: TemplateConfig) -> TemplateEntry:
    """Project a validated TemplateConfig into the public TemplateEntry shape."""
    meta = cfg.meta

    inputs = [_param_to_input(name, spec) for name, spec in cfg.params.items()]
    outputs = [
        OutputField(
            name=name,
            description=spec.description,
            tolerance=spec.tolerance,
        )
        for name, spec in cfg.outputs.items()
    ]

    long_desc = meta.long_description.strip() if meta.long_description else ""

    return TemplateEntry(
        task_id=meta.name,
        discipline=meta.discipline,  # type: ignore[arg-type]  — both sides use the same 5-literal
        category=meta.category,
        category_label=None,
        standards=list(meta.standards),
        inputs=inputs,
        outputs=outputs,
        task_name=_slug_to_title(meta.name),
        description=meta.description,
        long_description=long_desc or None,
        tags=list(meta.tags),
        tool_mode=meta.tool_mode.value,  # type: ignore[arg-type]  — StrEnum → literal
        difficulty_tiers=_sort_difficulty_tiers(list(cfg.difficulty.keys())),
        archetype_count=len(cfg.archetypes),
    )


def _seed_field_to_input(field: str | StructuredSeedField) -> InputField:
    """Map a plain string or StructuredSeedField to a public InputField."""
    if isinstance(field, str):
        return InputField(name=field)
    return InputField(
        name=field.name,
        unit=field.unit,
        type=field.type,  # type: ignore[arg-type]  — StructuredSeedField.type matches InputField.type subset
    )


def _seed_field_to_output(field: str | StructuredSeedField) -> OutputField:
    """Map a plain string or StructuredSeedField to a public OutputField."""
    if isinstance(field, str):
        return OutputField(name=field)
    return OutputField(name=field.name, unit=field.unit)


def _project_seed(seed: SeedTask) -> SeedEntry:
    """Project a validated SeedTask into the public SeedEntry shape."""
    src = seed.source

    return SeedEntry(
        task_id=src.task_id,
        discipline=src.discipline,  # type: ignore[arg-type]  — both sides use the same 5-literal
        category=src.category_id or src.task_id,
        category_label=src.category_name,
        standards=list(src.standards),
        inputs=[_seed_field_to_input(f) for f in src.inputs],
        outputs=[_seed_field_to_output(f) for f in src.outputs],
        task_name=src.task_name,
        description=src.description,
        complexity=src.complexity,
    )


def _is_holdout_template(cfg: TemplateConfig) -> bool:
    """Return True if the template should be excluded from the public catalogue.

    Templates do not yet carry a holdout/visibility field — this is a forward-compat
    predicate. Once TemplateMeta grows a visibility flag, update this to read it.
    """
    return False


def _is_holdout_seed(seed: SeedTask) -> bool:
    """Return True if the seed should be excluded from the public catalogue.

    Seeds do not yet carry a holdout/visibility field — this is a forward-compat
    predicate. Once SeedSource grows a visibility flag, update this to read it.
    """
    return False


def _git_short_sha(cwd: Path) -> str | None:
    """Return the short git SHA of HEAD, or None if not a repo / git unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def _scan_templates_in_root(
    templates_root: Path,
) -> list[tuple[TemplateConfig, Path]]:
    """Load every valid template directly beneath ``templates_root``.

    Mirrors the inner loop of ``templates.registry.discover_templates`` but without
    the built-in-directory merging, so tests can stage tmp-path trees in isolation.
    Silently skips individual templates that fail to load — matches registry behaviour.
    """
    if not templates_root.is_dir():
        return []
    found: list[tuple[TemplateConfig, Path]] = []
    for engine_path in sorted(templates_root.rglob("engine.py")):
        candidate = engine_path.parent
        try:
            cfg, _ = load_template(candidate)
        except (FileNotFoundError, ValueError):
            continue
        found.append((cfg, candidate))
    return found


def build_catalogue(
    *,
    templates_root: Path,
    tasks_root: Path,
    library_version: str,
    library_commit: str | None = None,
    now: datetime | None = None,
) -> tuple[LibraryCatalogue, ExportDiagnostics]:
    """Build the library catalogue from templates and seeds on disk.

    Raises DuplicateTemplateError if two templates share (discipline, task_id).
    Raises ValueError if both templates and seeds are empty (misconfiguration signal).
    Soft-skips malformed seeds and duplicate seeds — counted in diagnostics, never fatal.
    """
    loaded_templates = _scan_templates_in_root(templates_root)
    loaded_seeds, skipped_seeds = load_seeds(tasks_root)

    if not loaded_templates and not loaded_seeds:
        msg = "library export is empty: no templates or seeds found"
        raise ValueError(msg)

    # --- Templates: detect dupes, apply holdout filter, project ---
    template_keys: set[tuple[str, str]] = set()
    template_entries: list[TemplateEntry] = []
    for cfg, _path in loaded_templates:
        if _is_holdout_template(cfg):
            continue
        key = (cfg.meta.discipline, cfg.meta.name)
        if key in template_keys:
            msg = f"duplicate template: {cfg.meta.discipline}/{cfg.meta.name}"
            raise DuplicateTemplateError(msg)
        template_keys.add(key)
        template_entries.append(_project_template(cfg))

    # --- Seeds: suppress template-matched, holdout, and duplicate seeds ---
    seed_keys: set[tuple[str, str]] = set()
    seed_entries: list[SeedEntry] = []
    for seed in loaded_seeds:
        if _is_holdout_seed(seed):
            continue
        key = (seed.source.discipline, seed.source.task_id)
        if key in template_keys:
            # Approach A: template wins, seed suppressed silently (not a skip).
            continue
        if key in seed_keys:
            skipped_seeds.append(
                SkippedEntry(
                    path=Path(f"{seed.source.discipline}/{seed.source.task_id}"),
                    reason=f"duplicate seed key: {key[0]}/{key[1]}",
                    kind="seed",
                )
            )
            continue
        seed_keys.add(key)
        seed_entries.append(_project_seed(seed))

    # --- Sort by (discipline, category, task_id) for deterministic output ---
    template_entries.sort(key=lambda e: (e.discipline, e.category, e.task_id))
    seed_entries.sort(key=lambda e: (e.discipline, e.category, e.task_id))

    counts = _compute_counts(template_entries, seed_entries)

    catalogue = LibraryCatalogue(
        generated_at=now or datetime.now(UTC),
        library_version=library_version,
        library_commit=library_commit,
        templates=template_entries,
        seeds=seed_entries,
        counts=counts,
    )

    diagnostics = ExportDiagnostics(
        skipped_templates=[],  # discover_templates already silently drops; future: enrich.
        skipped_seeds=skipped_seeds,
    )

    return catalogue, diagnostics


def _compute_counts(templates: list[TemplateEntry], seeds: list[SeedEntry]) -> CatalogueCounts:
    """Derive per-discipline and total counts from the finalised entry lists."""
    by_discipline: dict[str, dict[str, int]] = {}
    for t in templates:
        by_discipline.setdefault(t.discipline, {"templates": 0, "seeds": 0})
        by_discipline[t.discipline]["templates"] += 1
    for s in seeds:
        by_discipline.setdefault(s.discipline, {"templates": 0, "seeds": 0})
        by_discipline[s.discipline]["seeds"] += 1
    return CatalogueCounts(
        total_templates=len(templates),
        total_seeds=len(seeds),
        by_discipline=by_discipline,
    )
