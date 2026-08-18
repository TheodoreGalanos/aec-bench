# ABOUTME: Builds the public library catalogue from template and seed source.
# ABOUTME: Projection layer — reads templates via registry, loads seeds, validates.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from aec_bench.contracts.library_catalogue import (
    InputField,
    LibraryCatalogue,
    OutputField,
    SeedEntry,
    TemplateEntry,
)
from aec_bench.contracts.seed_task import SeedTask, StructuredSeedField
from aec_bench.templates.contracts import ParamSpec, TemplateConfig
from aec_bench.templates.registry import discover_templates

type _CatalogueDiscipline = Literal["civil", "electrical", "ground", "maritime", "mechanical", "structural"]
type _CatalogueInputType = Literal["float", "int", "enum", "categorical"]


@dataclass(frozen=True)
class SkippedEntry:
    """Diagnostic record for a template or seed that was skipped during export."""

    path: Path
    reason: str
    kind: Literal["template", "seed"]


@dataclass(frozen=True, slots=True)
class LoadedSeed:
    """Validated seed plus the directory that supplied it."""

    seed: SeedTask
    path: Path

    @property
    def discipline(self) -> str:
        return self.seed.source.discipline

    @property
    def category(self) -> str:
        return self.seed.source.category_id or self.path.parent.name

    @property
    def task_id(self) -> str:
        return self.seed.source.task_id

    @property
    def task_name(self) -> str:
        return self.seed.source.task_name

    @property
    def description(self) -> str:
        return self.seed.source.description

    @property
    def complexity(self) -> str:
        return self.seed.source.complexity

    @property
    def standards(self) -> tuple[str, ...]:
        return tuple(self.seed.source.standards)

    @property
    def inputs(self) -> tuple[str, ...]:
        return tuple(value if isinstance(value, str) else value.name for value in self.seed.source.inputs)

    @property
    def outputs(self) -> tuple[str, ...]:
        return tuple(value if isinstance(value, str) else value.name for value in self.seed.source.outputs)


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


def load_seeds(tasks_root: Path) -> tuple[list[LoadedSeed], list[SkippedEntry]]:
    """Walk tasks_root for source_task.json files and validate each against SeedTask.

    Returns (valid_seeds, skipped_entries). Malformed or schema-violating files
    land in skipped_entries with a reason string — they never fail the scan.
    """
    if not tasks_root.is_dir():
        return [], []

    valid: list[LoadedSeed] = []
    skipped: list[SkippedEntry] = []

    for path in sorted(tasks_root.rglob("source_task.json")):
        try:
            seed = SeedTask.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            skipped.append(
                SkippedEntry(
                    path=path,
                    reason=str(exc),
                    kind="seed",
                )
            )
            continue

        valid.append(LoadedSeed(seed=seed, path=path.parent))

    return valid, skipped


def _param_to_input(name: str, spec: ParamSpec) -> InputField:
    """Map a single ParamSpec to a public InputField."""
    return InputField(
        name=name,
        description=spec.description,
        unit=spec.unit,
        type=spec.type.value,  # ParamType is a catalogue input-type subset.
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
        discipline=cast(_CatalogueDiscipline, meta.discipline),
        category=meta.category,
        category_label=None,
        standards=sorted(meta.standards),
        inputs=inputs,
        outputs=outputs,
        task_name=_slug_to_title(meta.name),
        description=meta.description,
        long_description=long_desc or None,
        tags=sorted(meta.tags),
        tool_mode=meta.tool_mode.value,
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
        type=cast(_CatalogueInputType, field.type),
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
        discipline=src.discipline,
        category=src.category_id or src.task_id,
        category_label=src.category_name,
        standards=sorted(src.standards),
        inputs=[_seed_field_to_input(f) for f in src.inputs],
        outputs=[_seed_field_to_output(f) for f in src.outputs],
        task_name=src.task_name,
        description=src.description,
        complexity=src.complexity,
    )


def catalogue_json_bytes(catalogue: LibraryCatalogue, *, pretty: bool = False) -> bytes:
    """Return deterministic UTF-8 catalogue JSON with one final newline."""
    payload = catalogue.model_dump(mode="json")
    if pretty:
        serialised = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    else:
        serialised = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"{serialised}\n".encode()


def build_catalogue(
    *,
    templates_root: Path,
    tasks_root: Path,
) -> tuple[LibraryCatalogue, ExportDiagnostics]:
    """Build the library catalogue from templates and seeds on disk.

    Raises DuplicateTemplateError if two templates share (discipline, task_id).
    Raises ValueError if both templates and seeds are empty (misconfiguration signal).
    Soft-skips malformed seeds and duplicate seeds — counted in diagnostics, never fatal.
    """
    loaded_templates, template_diagnostics = discover_templates(
        user_dirs=[templates_root],
        include_builtin=False,
    )
    loaded_seeds, skipped_seeds = load_seeds(tasks_root)

    if not loaded_templates and not loaded_seeds:
        msg = "library export is empty: no templates or seeds found"
        raise ValueError(msg)

    # The caller supplies the public template and seed roots; sealed material is not scanned.
    template_keys: set[tuple[str, str]] = set()
    template_entries: list[TemplateEntry] = []
    for template in loaded_templates:
        cfg = template.config
        key = (cfg.meta.discipline, cfg.meta.name)
        if key in template_keys:
            msg = f"duplicate template: {cfg.meta.discipline}/{cfg.meta.name}"
            raise DuplicateTemplateError(msg)
        template_keys.add(key)
        template_entries.append(_project_template(cfg))

    # Suppress template-matched and duplicate seeds.
    seed_keys: set[tuple[str, str]] = set()
    seed_entries: list[SeedEntry] = []
    for loaded_seed in loaded_seeds:
        seed = loaded_seed.seed
        key = (seed.source.discipline, seed.source.task_id)
        if key in template_keys:
            # Approach A: template wins, seed suppressed silently (not a skip).
            continue
        if key in seed_keys:
            skipped_seeds.append(
                SkippedEntry(
                    path=loaded_seed.path,
                    reason=f"duplicate seed key: {key[0]}/{key[1]}",
                    kind="seed",
                )
            )
            continue
        seed_keys.add(key)
        seed_entries.append(_project_seed(seed))

    # The stable public entry identity is the discipline and task ID pair.
    template_entries.sort(key=lambda entry: (entry.discipline, entry.task_id))
    seed_entries.sort(key=lambda entry: (entry.discipline, entry.task_id))

    catalogue = LibraryCatalogue(
        templates=template_entries,
        seeds=seed_entries,
    )

    diagnostics = ExportDiagnostics(
        skipped_templates=[
            SkippedEntry(path=diagnostic.path, reason=diagnostic.error, kind="template")
            for diagnostic in template_diagnostics
        ],
        skipped_seeds=skipped_seeds,
    )

    return catalogue, diagnostics
