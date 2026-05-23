# ABOUTME: Tests for library_export projection — types, seed loader, and build_catalogue.
# ABOUTME: Uses real tmp_path fixtures, never mocks the filesystem.

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from aec_bench.contracts.library_catalogue import LibraryCatalogue, SeedEntry, TemplateEntry
from aec_bench.contracts.seed_task import SeedSource, SeedTask, StructuredSeedField
from aec_bench.tasks.library_export import (
    DuplicateTemplateError,
    ExportDiagnostics,
    SkippedEntry,
    _git_short_sha,
    _is_holdout_seed,
    _is_holdout_template,
    _project_seed,
    _project_template,
    build_catalogue,
    load_seeds,
)
from aec_bench.templates.contracts import (
    ArchetypeRange,
    ArchetypeSpec,
    DifficultyPreset,
    OutputSpec,
    ParamSpec,
    ParamType,
    TemplateConfig,
    TemplateMeta,
    ToolMode,
    VisibilityLevel,
)


def test_skipped_entry_is_frozen_dataclass() -> None:
    s = SkippedEntry(path=Path("/tmp/x"), reason="missing file", kind="template")
    assert s.path == Path("/tmp/x")
    assert s.reason == "missing file"
    assert s.kind == "template"
    with pytest.raises(AttributeError):
        s.reason = "something else"  # type: ignore[misc]


def test_export_diagnostics_empty() -> None:
    d = ExportDiagnostics(skipped_templates=[], skipped_seeds=[])
    assert d.skipped_templates == []
    assert d.skipped_seeds == []


def test_duplicate_template_error_is_value_error() -> None:
    err = DuplicateTemplateError("duplicate template: electrical/voltage-drop")
    assert isinstance(err, ValueError)
    assert "duplicate" in str(err)


def _write_seed(dest: Path, data: dict) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data), encoding="utf-8")


def _valid_seed(task_id: str = "t1", discipline: str = "electrical") -> dict:
    return {
        "status": "proposed",
        "seed_origin": "expert",
        "source": {
            "discipline": discipline,
            "task_id": task_id,
            "task_name": task_id,
            "description": "d",
            "inputs": ["i"],
            "outputs": ["o"],
            "standards": ["s"],
            "complexity": "low",
        },
    }


def test_load_seeds_returns_empty_when_root_missing(tmp_path: Path) -> None:
    seeds, skipped = load_seeds(tmp_path / "nonexistent")
    assert seeds == []
    assert skipped == []


def test_load_seeds_loads_valid_seed(tmp_path: Path) -> None:
    _write_seed(tmp_path / "electrical" / "cat1" / "t1" / "source_task.json", _valid_seed())
    seeds, skipped = load_seeds(tmp_path)
    assert len(seeds) == 1
    assert seeds[0].source.task_id == "t1"
    assert skipped == []


def test_load_seeds_skips_malformed_json(tmp_path: Path) -> None:
    bad = tmp_path / "electrical" / "broken" / "source_task.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not valid json", encoding="utf-8")
    seeds, skipped = load_seeds(tmp_path)
    assert seeds == []
    assert len(skipped) == 1
    assert skipped[0].kind == "seed"
    assert "json" in skipped[0].reason.lower() or "decode" in skipped[0].reason.lower()


def test_load_seeds_skips_schema_violations(tmp_path: Path) -> None:
    bad_seed = _valid_seed()
    bad_seed["source"]["discipline"] = "hvac"  # not in the enum
    _write_seed(tmp_path / "x" / "source_task.json", bad_seed)
    seeds, skipped = load_seeds(tmp_path)
    assert seeds == []
    assert len(skipped) == 1
    assert skipped[0].kind == "seed"


def test_load_seeds_finds_nested_seeds(tmp_path: Path) -> None:
    _write_seed(tmp_path / "electrical" / "a" / "s1" / "source_task.json", _valid_seed("s1"))
    _write_seed(tmp_path / "civil" / "b" / "s2" / "source_task.json", _valid_seed("s2", "civil"))
    seeds, skipped = load_seeds(tmp_path)
    assert {s.source.task_id for s in seeds} == {"s1", "s2"}
    assert skipped == []


def test_load_seeds_returns_stable_order(tmp_path: Path) -> None:
    # Files are sorted by Path for determinism.
    for tid in ["z", "a", "m"]:
        _write_seed(tmp_path / tid / "source_task.json", _valid_seed(tid))
    seeds1, _ = load_seeds(tmp_path)
    seeds2, _ = load_seeds(tmp_path)
    assert [s.source.task_id for s in seeds1] == [s.source.task_id for s in seeds2]


def _make_template_config() -> TemplateConfig:
    return TemplateConfig(
        meta=TemplateMeta(
            name="voltage-drop",
            description="Cable voltage drop",
            long_description="long desc",
            discipline="electrical",
            category="cable-sizing",
            standards=["AS/NZS 3008.1.1"],
            tags=["electrical", "cable-sizing"],
            tool_mode=ToolMode.WITH_TOOL,
        ),
        params={
            "length_m": ParamSpec(
                type=ParamType.FLOAT,
                description="Cable length",
                unit="m",
                min_value=1,
                max_value=500,
            ),
        },
        outputs={
            "voltage_drop_percent": OutputSpec(
                description="Voltage drop %",
                tolerance=0.03,
            ),
        },
        archetypes={
            "residential": ArchetypeSpec(
                description="r",
                site_contexts=["sydney"],
                params={"length_m": ArchetypeRange(min=5, max=30)},
            ),
        },
        difficulty={
            "easy": DifficultyPreset(
                description="e",
                visibility=VisibilityLevel.ALL_GIVEN,
                archetypes=["residential"],
            ),
            "medium": DifficultyPreset(
                description="m",
                visibility=VisibilityLevel.ALL_GIVEN,
                archetypes=["residential"],
            ),
        },
    )


def test_project_template_basic() -> None:
    entry = _project_template(_make_template_config())
    assert isinstance(entry, TemplateEntry)
    assert entry.task_id == "voltage-drop"
    assert entry.discipline == "electrical"
    assert entry.category == "cable-sizing"
    assert entry.category_label is None
    assert entry.standards == ["AS/NZS 3008.1.1"]
    # task_name is derived from the slug — title-cased with separators replaced.
    assert entry.task_name == "Voltage Drop"
    assert entry.description == "Cable voltage drop"
    assert entry.long_description == "long desc"
    assert entry.tool_mode == "with-tool"


def test_project_template_inputs_map_params() -> None:
    entry = _project_template(_make_template_config())
    assert len(entry.inputs) == 1
    assert entry.inputs[0].name == "length_m"
    assert entry.inputs[0].description == "Cable length"
    assert entry.inputs[0].unit == "m"
    assert entry.inputs[0].type == "float"


def test_project_template_outputs_map_with_tolerance() -> None:
    entry = _project_template(_make_template_config())
    assert len(entry.outputs) == 1
    assert entry.outputs[0].name == "voltage_drop_percent"
    assert entry.outputs[0].tolerance == 0.03


def test_project_template_difficulty_tiers_sorted() -> None:
    entry = _project_template(_make_template_config())
    # Canonical difficulty order is easy → medium → hard (not alphabetical).
    assert entry.difficulty_tiers == ["easy", "medium"]


def test_project_template_difficulty_tiers_canonical_order() -> None:
    """Three tiers sort easy → medium → hard, not alphabetical (easy, hard, medium)."""
    cfg = _make_template_config()
    extra_hard = DifficultyPreset(
        description="h",
        visibility=VisibilityLevel.ALL_GIVEN,
        archetypes=["residential"],
    )
    cfg = cfg.model_copy(update={"difficulty": {**cfg.difficulty, "hard": extra_hard}})
    entry = _project_template(cfg)
    assert entry.difficulty_tiers == ["easy", "medium", "hard"]


def test_project_template_unknown_tier_names_sort_last() -> None:
    """Non-canonical tier names (e.g. 'expert') appear after the canonical set."""
    cfg = _make_template_config()
    expert = DifficultyPreset(
        description="x",
        visibility=VisibilityLevel.ALL_GIVEN,
        archetypes=["residential"],
    )
    cfg = cfg.model_copy(update={"difficulty": {**cfg.difficulty, "expert": expert}})
    entry = _project_template(cfg)
    # easy, medium come first (canonical), then "expert" alphabetically.
    assert entry.difficulty_tiers == ["easy", "medium", "expert"]


def test_project_template_task_name_title_cases_underscores_and_hyphens() -> None:
    """Slug-to-title handles both 'voltage-drop' and 'voltage_drop' consistently."""
    cfg = _make_template_config()
    cfg = cfg.model_copy(update={"meta": cfg.meta.model_copy(update={"name": "hudson-armor_sizing"})})
    entry = _project_template(cfg)
    assert entry.task_name == "Hudson Armor Sizing"
    # task_id still carries the slug verbatim.
    assert entry.task_id == "hudson-armor_sizing"


def test_project_template_archetype_count() -> None:
    entry = _project_template(_make_template_config())
    assert entry.archetype_count == 1


def test_project_template_empty_long_description_becomes_none() -> None:
    cfg = _make_template_config()
    cfg = cfg.model_copy(update={"meta": cfg.meta.model_copy(update={"long_description": ""})})
    entry = _project_template(cfg)
    assert entry.long_description is None


def test_project_template_no_archetypes_or_difficulties() -> None:
    cfg = _make_template_config()
    cfg = cfg.model_copy(update={"archetypes": {}, "difficulty": {}})
    entry = _project_template(cfg)
    assert entry.archetype_count == 0
    assert entry.difficulty_tiers == []


def _make_seed_plain() -> SeedTask:
    return SeedTask(
        status="proposed",
        seed_origin="ngnbench",
        source=SeedSource(
            discipline="electrical",
            task_id="busbar-thermal",
            task_name="Busbar Thermal Sizing",
            description="Size busbar",
            inputs=["Continuous current (A)", "Material"],
            outputs=["Required cross-section (mm²)"],
            standards=["IEEE 605"],
            complexity="low",
            category_id="busbar-design",
            category_name="Busbar Design & Analysis",
        ),
    )


def test_project_seed_plain_inputs() -> None:
    entry = _project_seed(_make_seed_plain())
    assert isinstance(entry, SeedEntry)
    assert entry.task_id == "busbar-thermal"
    assert entry.discipline == "electrical"
    assert entry.category == "busbar-design"
    assert entry.category_label == "Busbar Design & Analysis"
    assert entry.complexity == "low"
    assert entry.task_name == "Busbar Thermal Sizing"
    # Plain strings become InputField with name only.
    assert len(entry.inputs) == 2
    assert entry.inputs[0].name == "Continuous current (A)"
    assert entry.inputs[0].description is None
    assert entry.inputs[0].unit is None
    assert entry.inputs[0].type is None


def test_project_seed_structured_inputs() -> None:
    seed = SeedTask(
        status="proposed",
        seed_origin="expert",
        source=SeedSource(
            discipline="civil",
            task_id="rational-method",
            task_name="Rational Method",
            description="d",
            inputs=[
                StructuredSeedField(name="area", type="float", unit="ha"),
                StructuredSeedField(name="type", type="categorical", values=["urban", "rural"]),
            ],
            outputs=[StructuredSeedField(name="peak_flow", type="float", unit="m3/s")],
            standards=["AR&R"],
            complexity="medium",
        ),
    )
    entry = _project_seed(seed)
    assert entry.inputs[0].name == "area"
    assert entry.inputs[0].unit == "ha"
    assert entry.inputs[0].type == "float"
    assert entry.inputs[1].type == "categorical"
    assert entry.outputs[0].name == "peak_flow"
    assert entry.outputs[0].unit == "m3/s"


def test_project_seed_missing_category_falls_back() -> None:
    seed = _make_seed_plain()
    seed = seed.model_copy(
        update={"source": seed.source.model_copy(update={"category_id": None, "category_name": None})}
    )
    entry = _project_seed(seed)
    # Fallback: category becomes the task_id (stable, non-empty).
    assert entry.category == "busbar-thermal"
    assert entry.category_label is None


def test_is_holdout_template_no_op_today() -> None:
    """Templates don't carry a holdout field yet — the predicate returns False for all."""
    cfg = _make_template_config()
    assert _is_holdout_template(cfg) is False


def test_is_holdout_seed_no_op_today() -> None:
    """Seeds don't carry a holdout field yet — the predicate returns False for all."""
    seed = _make_seed_plain()
    assert _is_holdout_seed(seed) is False


def test_git_short_sha_returns_none_outside_repo(tmp_path: Path) -> None:
    # tmp_path is not a git repo, so git rev-parse fails.
    assert _git_short_sha(cwd=tmp_path) is None


def test_git_short_sha_returns_short_sha_inside_repo() -> None:
    # Running against the actual repo — SHA should be 7+ hex chars.
    sha = _git_short_sha(cwd=Path.cwd())
    if sha is not None:  # allow None if the test env is not a git repo
        assert len(sha) >= 7
        assert all(c in "0123456789abcdef" for c in sha)


def test_git_short_sha_handles_git_not_installed() -> None:
    """If git binary is missing, return None — don't crash the export."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert _git_short_sha(cwd=Path.cwd()) is None


# --- Helpers to stage templates on disk in a tmp dir ---

TEMPLATE_PARAMS_TOML = """\
[meta]
name = "{name}"
description = "d"
discipline = "{discipline}"
category = "{category}"
standards = ["S1"]
tags = ["t1"]
tool_mode = "with-tool"

[params.x]
type = "float"
description = "x"
unit = "m"
min = 1
max = 10

[outputs.y]
description = "y"
tolerance = 0.03

[difficulty.easy]
description = "e"
visibility = "all_given"
archetypes = []
"""

TEMPLATE_ENGINE_PY = """\
def compute(**kwargs):
    return {"y": 1.0}
"""


def _stage_template(root: Path, name: str, discipline: str = "electrical", category: str = "cat1") -> None:
    tdir = root / discipline / name.replace("-", "_")
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "params.toml").write_text(
        TEMPLATE_PARAMS_TOML.format(name=name, discipline=discipline, category=category),
        encoding="utf-8",
    )
    (tdir / "engine.py").write_text(TEMPLATE_ENGINE_PY, encoding="utf-8")
    (tdir / "instruction.md").write_text("test instruction", encoding="utf-8")


def test_build_catalogue_happy_path(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    _stage_template(templates_root, "t-one", "electrical", "cat1")
    _stage_template(templates_root, "t-two", "civil", "cat2")
    _write_seed(tasks_root / "ground" / "s1" / "source_task.json", _valid_seed("s1", "ground"))

    cat, diag = build_catalogue(
        templates_root=templates_root,
        tasks_root=tasks_root,
        library_version="9.9.9",
        library_commit="deadbee",
        now=datetime(2026, 4, 19, 12, 0, tzinfo=UTC),
    )

    assert isinstance(cat, LibraryCatalogue)
    assert cat.library_version == "9.9.9"
    assert cat.library_commit == "deadbee"
    assert cat.generated_at == datetime(2026, 4, 19, 12, 0, tzinfo=UTC)
    assert len(cat.templates) == 2
    assert len(cat.seeds) == 1
    assert cat.counts.total_templates == 2
    assert cat.counts.total_seeds == 1
    assert diag.skipped_templates == []
    assert diag.skipped_seeds == []


def test_build_catalogue_dedupes_seed_matching_template(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    _stage_template(templates_root, "t-one", "electrical")
    # Seed shares (discipline, task_id) with the template — should be suppressed.
    seed_path = tasks_root / "electrical" / "t-one" / "source_task.json"
    _write_seed(seed_path, _valid_seed("t-one", "electrical"))

    cat, _ = build_catalogue(
        templates_root=templates_root,
        tasks_root=tasks_root,
        library_version="1",
        now=datetime(2026, 4, 19, tzinfo=UTC),
    )
    assert len(cat.templates) == 1
    assert len(cat.seeds) == 0


def test_build_catalogue_sort_stability(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    # Stage in non-alphabetical order.
    _stage_template(templates_root, "zebra", "electrical", "cat-b")
    _stage_template(templates_root, "alpha", "electrical", "cat-a")
    _stage_template(templates_root, "middle", "civil", "cat-a")

    cat, _ = build_catalogue(
        templates_root=templates_root,
        tasks_root=tasks_root,
        library_version="1",
        now=datetime(2026, 4, 19, tzinfo=UTC),
    )
    # Sorted by (discipline, category, task_id).
    assert [(t.discipline, t.category, t.task_id) for t in cat.templates] == [
        ("civil", "cat-a", "middle"),
        ("electrical", "cat-a", "alpha"),
        ("electrical", "cat-b", "zebra"),
    ]


def test_build_catalogue_deterministic_output(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    _stage_template(templates_root, "t1", "electrical")
    _write_seed(tasks_root / "civil" / "s1" / "source_task.json", _valid_seed("s1", "civil"))

    now = datetime(2026, 4, 19, tzinfo=UTC)
    kwargs = dict(templates_root=templates_root, tasks_root=tasks_root, library_version="1", now=now)
    cat1, _ = build_catalogue(**kwargs)
    cat2, _ = build_catalogue(**kwargs)
    assert cat1.model_dump_json() == cat2.model_dump_json()


def test_build_catalogue_duplicate_template_hard_fails(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    # Stage the same (discipline, task_id) twice under different directory names.
    _stage_template(templates_root, "dup", "electrical", "cat-a")
    # Second copy with same meta.name (name is derived from meta, not directory).
    other = templates_root / "electrical" / "duplicate_copy"
    other.mkdir(parents=True)
    (other / "params.toml").write_text(
        TEMPLATE_PARAMS_TOML.format(name="dup", discipline="electrical", category="cat-b"),
        encoding="utf-8",
    )
    (other / "engine.py").write_text(TEMPLATE_ENGINE_PY, encoding="utf-8")
    (other / "instruction.md").write_text("test", encoding="utf-8")

    with pytest.raises(DuplicateTemplateError, match="dup"):
        build_catalogue(
            templates_root=templates_root,
            tasks_root=tasks_root,
            library_version="1",
            now=datetime(2026, 4, 19, tzinfo=UTC),
        )


def test_build_catalogue_duplicate_seed_soft_skips(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    _write_seed(tasks_root / "a" / "source_task.json", _valid_seed("same", "electrical"))
    _write_seed(tasks_root / "b" / "source_task.json", _valid_seed("same", "electrical"))

    cat, diag = build_catalogue(
        templates_root=templates_root,
        tasks_root=tasks_root,
        library_version="1",
        now=datetime(2026, 4, 19, tzinfo=UTC),
    )
    # First kept, second counted as skipped.
    assert len(cat.seeds) == 1
    assert len(diag.skipped_seeds) == 1
    assert "duplicate" in diag.skipped_seeds[0].reason.lower()


def test_build_catalogue_empty_library_hard_fails(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    templates_root.mkdir()
    tasks_root.mkdir()
    with pytest.raises(ValueError, match="empty"):
        build_catalogue(
            templates_root=templates_root,
            tasks_root=tasks_root,
            library_version="1",
            now=datetime(2026, 4, 19, tzinfo=UTC),
        )


def test_build_catalogue_counts_match_lists(tmp_path: Path) -> None:
    templates_root = tmp_path / "templates"
    tasks_root = tmp_path / "tasks"
    _stage_template(templates_root, "t1", "electrical")
    _stage_template(templates_root, "t2", "electrical")
    _stage_template(templates_root, "t3", "civil")
    _write_seed(tasks_root / "ground" / "s1" / "source_task.json", _valid_seed("s1", "ground"))
    _write_seed(tasks_root / "civil" / "s2" / "source_task.json", _valid_seed("s2", "civil"))

    cat, _ = build_catalogue(
        templates_root=templates_root,
        tasks_root=tasks_root,
        library_version="1",
        now=datetime(2026, 4, 19, tzinfo=UTC),
    )
    assert cat.counts.total_templates == 3
    assert cat.counts.total_seeds == 2
    assert cat.counts.by_discipline["electrical"] == {"templates": 2, "seeds": 0}
    assert cat.counts.by_discipline["civil"] == {"templates": 1, "seeds": 1}
    assert cat.counts.by_discipline["ground"] == {"templates": 0, "seeds": 1}
