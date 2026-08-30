# ABOUTME: Unit tests for dataset composition: config parsing, budget allocation, and coverage.
# ABOUTME: Validates SuiteConfig models, template filtering, allocation algorithm, and manifest.

import json
import textwrap
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pydantic import ValidationError

from aec_bench.generation.application import load_generated_tasks, read_generated_task_set
from aec_bench.generation.dataset import (
    CompositionPlan,
    OutputConfig,
    SuiteConfig,
    allocate_budget,
    filter_templates,
    generate_instances,
    largest_remainder_round,
    load_suite_config,
    normalise_ratios,
    plan_suite,
)
from aec_bench.generation.replay import GenerationManifest
from aec_bench.templates.contracts import (
    DifficultyPreset,
    OutputSpec,
    TemplateConfig,
    TemplateMeta,
    ToolMode,
    VisibilityLevel,
)
from aec_bench.templates.registry import LoadedTemplate


def _nested_mapping_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | {key for item in value.values() for key in _nested_mapping_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _nested_mapping_keys(item)}
    return set()


def _parse_suite_toml(toml_str: str) -> SuiteConfig:
    """Helper: parse a TOML string into SuiteConfig."""
    raw = tomllib.loads(toml_str)
    return SuiteConfig.model_validate(raw)


MINIMAL_SUITE_TOML = textwrap.dedent("""\
    name = "test-suite"
    seed = 42
    task_lifecycle = "proposed"
    task_visibility = "public"

    [coverage]
    difficulties = {easy = 0.5, medium = 0.5}
    min_tasks_per_discipline = 1

    [templates]
    include = ["*/*"]

    [visibility]
    mix = {all_given = 1.0}

    [tool_mode]
    mix = {with_tool = 1.0}

    [instances]
    per_task = 3
    total_max = 100

    [output]
    dir = "./tasks/"
""")


def test_parse_minimal_suite_config() -> None:
    """A well-formed minimal suite.toml should parse into SuiteConfig."""
    config = _parse_suite_toml(MINIMAL_SUITE_TOML)
    assert config.name == "test-suite"
    assert config.seed == 42
    assert config.coverage.difficulties == {"easy": 0.5, "medium": 0.5}
    assert config.coverage.min_tasks_per_discipline == 1
    assert config.instances.per_task == 3
    assert config.instances.total_max == 100


def test_suite_config_rejects_missing_name() -> None:
    """SuiteConfig without a name should fail validation."""
    bad = MINIMAL_SUITE_TOML.replace('name = "test-suite"\n', "")
    with pytest.raises(ValidationError):
        _parse_suite_toml(bad)


def test_suite_config_defaults() -> None:
    """Fields with defaults should be populated when omitted."""
    toml_str = textwrap.dedent("""\
        name = "defaults-test"
        task_lifecycle = "proposed"
        task_visibility = "public"
        seed = 1

        [coverage]
        difficulties = {easy = 1.0}

        [templates]

        [visibility]
        mix = {all_given = 1.0}

        [tool_mode]
        mix = {with_tool = 1.0}

        [instances]

        [output]
    """)
    config = _parse_suite_toml(toml_str)
    assert config.templates.include == ["*/*"]
    assert config.instances.per_task == 5
    assert config.instances.total_max == 200


def test_tool_mode_keys_normalised() -> None:
    """TOML underscored keys (with_tool) should normalise to ToolMode enum values (with-tool)."""
    config = _parse_suite_toml(MINIMAL_SUITE_TOML)
    normalised = config.tool_mode_normalised()
    assert "with-tool" in normalised


# --- Task 2: Normalise/Largest-Remainder Helpers ---


def test_normalise_ratios_already_sum_to_one() -> None:
    """Ratios summing to 1.0 should be returned unchanged."""
    ratios = {"a": 0.4, "b": 0.6}
    result, warning = normalise_ratios(ratios)
    assert result == pytest.approx({"a": 0.4, "b": 0.6})
    assert warning is None


def test_normalise_ratios_scales_to_one() -> None:
    """Ratios summing to 2.0 should be halved."""
    ratios = {"a": 1.0, "b": 1.0}
    result, warning = normalise_ratios(ratios)
    assert result == pytest.approx({"a": 0.5, "b": 0.5})
    assert warning is not None


def test_normalise_ratios_returns_warning_for_deviation() -> None:
    """Ratios far from 1.0 should emit a warning string."""
    ratios = {"a": 0.3, "b": 0.3}
    result, warning = normalise_ratios(ratios)
    assert warning is not None
    assert result == pytest.approx({"a": 0.5, "b": 0.5})


def test_largest_remainder_round_basic() -> None:
    """5 items with 40/40/20 split should give 2, 2, 1."""
    result = largest_remainder_round({"easy": 0.4, "medium": 0.4, "hard": 0.2}, total=5)
    assert result == {"easy": 2, "medium": 2, "hard": 1}


def test_largest_remainder_round_all_to_one() -> None:
    """3 items across 3 categories with equal weights should give 1 each."""
    result = largest_remainder_round({"a": 1.0, "b": 1.0, "c": 1.0}, total=3)
    assert result == {"a": 1, "b": 1, "c": 1}


def test_largest_remainder_round_zero_total() -> None:
    """Zero total should give all zeros."""
    result = largest_remainder_round({"a": 0.5, "b": 0.5}, total=0)
    assert result == {"a": 0, "b": 0}


def test_largest_remainder_round_one_item() -> None:
    """Single item gets the entire total."""
    result = largest_remainder_round({"only": 1.0}, total=7)
    assert result == {"only": 7}


# --- Task 3: Template Filtering ---


def _loaded_template(config: TemplateConfig, path: Path) -> LoadedTemplate:
    engine = ModuleType(f"test_engine_{config.meta.name}")
    engine.compute = lambda **_kwargs: {name: 0.0 for name in config.outputs}
    return LoadedTemplate(
        config=config,
        path=path,
        engine=engine,
        engine_source="def compute(**kwargs): ...",
    )


def _make_template(name: str, discipline: str) -> LoadedTemplate:
    """Build a minimal TemplateConfig stub for testing."""
    meta = TemplateMeta(
        name=name,
        description=f"Test {name}",
        discipline=discipline,
        category="test-category",
        tool_mode=ToolMode.WITH_TOOL,
    )
    config = TemplateConfig(
        meta=meta,
        params={},
        outputs={},
    )
    return _loaded_template(config, Path(f"/fake/{discipline}/{name}"))


def test_filter_templates_wildcard_matches_all() -> None:
    """Include pattern '*/*' should match all templates."""
    templates = [
        _make_template("terzaghi", "ground"),
        _make_template("beam-bending", "structural"),
    ]
    result = filter_templates(templates, include=["*/*"])
    assert len(result) == 2


def test_filter_templates_discipline_glob() -> None:
    """Include pattern 'ground/*' should match only ground templates."""
    templates = [
        _make_template("terzaghi", "ground"),
        _make_template("beam-bending", "structural"),
    ]
    result = filter_templates(templates, include=["ground/*"])
    assert len(result) == 1
    assert result[0].config.meta.name == "terzaghi"


def test_filter_templates_name_glob() -> None:
    """Include pattern 'ground/terz*' should match terzaghi."""
    templates = [
        _make_template("terzaghi", "ground"),
        _make_template("meyerhof", "ground"),
    ]
    result = filter_templates(templates, include=["ground/terz*"])
    assert len(result) == 1
    assert result[0].config.meta.name == "terzaghi"


def test_filter_templates_multiple_patterns() -> None:
    """Multiple include patterns should OR together."""
    templates = [
        _make_template("terzaghi", "ground"),
        _make_template("beam-bending", "structural"),
        _make_template("heat-load", "mechanical"),
    ]
    result = filter_templates(templates, include=["ground/*", "structural/*"])
    assert len(result) == 2


def test_filter_templates_no_match_raises() -> None:
    """If no templates match, raise ValueError."""
    templates = [_make_template("terzaghi", "ground")]
    with pytest.raises(ValueError, match="No templates matched"):
        filter_templates(templates, include=["nonexistent/*"])


# --- Task 4: Budget Allocation ---


def test_allocate_budget_no_trim() -> None:
    """When total_max >= demand, each template gets per_task."""
    templates = [
        _make_template("a", "ground"),
        _make_template("b", "ground"),
    ]
    result, warnings = allocate_budget(templates, per_task=5, total_max=100, min_per_discipline=1)
    assert result == {"a": 5, "b": 5}
    assert warnings == []


def test_allocate_budget_proportional_trim_same_discipline() -> None:
    """3 templates in same discipline, per_task=5, total_max=9 -> 3 each."""
    templates = [
        _make_template("a", "ground"),
        _make_template("b", "ground"),
        _make_template("c", "ground"),
    ]
    result, _ = allocate_budget(templates, per_task=5, total_max=9, min_per_discipline=1)
    assert sum(result.values()) == 9
    assert result == {"a": 3, "b": 3, "c": 3}


def test_allocate_budget_discipline_guarantee() -> None:
    """Structural (1 template) should get at least min_per_discipline instances."""
    templates = [
        _make_template("a", "ground"),
        _make_template("b", "ground"),
        _make_template("c", "ground"),
        _make_template("d", "structural"),
    ]
    result, _ = allocate_budget(templates, per_task=5, total_max=10, min_per_discipline=3)
    assert result["d"] >= 3
    assert sum(result.values()) == 10


def test_allocate_budget_impossible_guarantee() -> None:
    """total_max < sum of discipline minimums -> distributes evenly, returns warnings."""
    templates = [
        _make_template("a", "ground"),
        _make_template("b", "structural"),
        _make_template("c", "electrical"),
    ]
    result, warnings = allocate_budget(templates, per_task=5, total_max=4, min_per_discipline=3)
    assert sum(result.values()) <= 4
    assert len(warnings) > 0


def test_allocate_budget_single_template() -> None:
    """Single template gets min(per_task, total_max)."""
    templates = [_make_template("only", "ground")]
    result, _ = allocate_budget(templates, per_task=5, total_max=3, min_per_discipline=1)
    assert result == {"only": 3}


# --- Task 5: plan_suite ---


def _make_template_with_difficulty(
    name: str,
    discipline: str,
    difficulties: dict[str, VisibilityLevel],
    tool_mode: ToolMode = ToolMode.WITH_TOOL,
) -> LoadedTemplate:
    """Build a TemplateConfig with specified difficulty presets."""
    meta = TemplateMeta(
        name=name,
        description=f"Test {name}",
        discipline=discipline,
        category="test-category",
        tool_mode=tool_mode,
    )
    diff_presets = {}
    for diff_name, vis in difficulties.items():
        hidden = ["param_a"] if vis == VisibilityLevel.PARTIAL else []
        diff_presets[diff_name] = DifficultyPreset(
            description=f"{diff_name} preset",
            visibility=vis,
            archetypes=["test_arch"],
            hidden_params=hidden,
        )
    config = TemplateConfig(
        meta=meta,
        params={},
        outputs={"result": OutputSpec(description="test output")},
        difficulty=diff_presets,
    )
    return _loaded_template(config, Path(f"/fake/{discipline}/{name}"))


def test_plan_suite_basic() -> None:
    """plan_suite with one template should produce correct number of planned instances."""
    templates = [
        _make_template_with_difficulty("t1", "ground", {"easy": VisibilityLevel.ALL_GIVEN}),
    ]
    config = _parse_suite_toml(MINIMAL_SUITE_TOML)
    plan = plan_suite(config, templates)
    assert isinstance(plan, CompositionPlan)
    assert len(plan.planned_instances) == config.instances.per_task


def test_plan_suite_preserves_duplicate_template_names() -> None:
    """Templates with the same name in different disciplines should not collapse."""
    templates = [
        _make_template_with_difficulty("shared", "civil", {"easy": VisibilityLevel.ALL_GIVEN}),
        _make_template_with_difficulty("shared", "ground", {"easy": VisibilityLevel.ALL_GIVEN}),
    ]
    config = _parse_suite_toml(MINIMAL_SUITE_TOML)
    plan = plan_suite(config, templates)

    assert len(plan.planned_instances) == config.instances.per_task * len(templates)
    assert plan.summary.by_discipline == {"civil": 3, "ground": 3}


def test_plan_suite_difficulty_distribution() -> None:
    """Instances should be distributed across difficulties per coverage ratios."""
    templates = [
        _make_template_with_difficulty(
            "t1",
            "ground",
            {"easy": VisibilityLevel.ALL_GIVEN, "medium": VisibilityLevel.ALL_GIVEN},
        ),
    ]
    toml_str = MINIMAL_SUITE_TOML.replace("per_task = 3", "per_task = 10")
    config = _parse_suite_toml(toml_str)
    plan = plan_suite(config, templates)
    diffs = [p.difficulty for p in plan.planned_instances]
    assert diffs.count("easy") == 5
    assert diffs.count("medium") == 5


def test_plan_suite_skips_undefined_difficulty() -> None:
    """If template doesn't define 'hard', its share is redistributed."""
    templates = [
        _make_template_with_difficulty(
            "t1",
            "ground",
            {"easy": VisibilityLevel.ALL_GIVEN, "medium": VisibilityLevel.ALL_GIVEN},
        ),
    ]
    toml_str = MINIMAL_SUITE_TOML.replace(
        "difficulties = {easy = 0.5, medium = 0.5}",
        "difficulties = {easy = 0.4, medium = 0.4, hard = 0.2}",
    ).replace("per_task = 3", "per_task = 5")
    config = _parse_suite_toml(toml_str)
    plan = plan_suite(config, templates)
    diffs = [p.difficulty for p in plan.planned_instances]
    assert "hard" not in diffs
    assert len(diffs) == 5


def test_plan_suite_tool_mode_fixed_template() -> None:
    """Template with tool_mode='with-tool' should give all instances 'with-tool'."""
    templates = [
        _make_template_with_difficulty(
            "t1",
            "ground",
            {"easy": VisibilityLevel.ALL_GIVEN},
            tool_mode=ToolMode.WITH_TOOL,
        ),
    ]
    config = _parse_suite_toml(MINIMAL_SUITE_TOML)
    plan = plan_suite(config, templates)
    assert all(p.tool_mode == "with-tool" for p in plan.planned_instances)


def test_plan_suite_tool_mode_both_template() -> None:
    """Template with tool_mode='both' should distribute per mix ratios."""
    templates = [
        _make_template_with_difficulty(
            "t1",
            "ground",
            {"easy": VisibilityLevel.ALL_GIVEN},
            tool_mode=ToolMode.BOTH,
        ),
    ]
    toml_str = MINIMAL_SUITE_TOML.replace(
        "mix = {with_tool = 1.0}",
        "mix = {with_tool = 0.5, no_tool = 0.5}",
    ).replace("per_task = 3", "per_task = 4")
    config = _parse_suite_toml(toml_str)
    plan = plan_suite(config, templates)
    modes = [p.tool_mode for p in plan.planned_instances]
    assert modes.count("with-tool") == 2
    assert modes.count("no-tool") == 2


def test_plan_suite_deterministic() -> None:
    """Same config + templates + seed should produce identical plans."""
    templates = [
        _make_template_with_difficulty("t1", "ground", {"easy": VisibilityLevel.ALL_GIVEN}),
    ]
    config = _parse_suite_toml(MINIMAL_SUITE_TOML)
    plan_a = plan_suite(config, templates)
    plan_b = plan_suite(config, templates)
    assert plan_a.planned_instances == plan_b.planned_instances


def test_plan_suite_seed_offsets_are_unique() -> None:
    """Every planned instance should have a unique seed_offset."""
    templates = [
        _make_template_with_difficulty("t1", "ground", {"easy": VisibilityLevel.ALL_GIVEN}),
        _make_template_with_difficulty("t2", "ground", {"easy": VisibilityLevel.ALL_GIVEN}),
    ]
    toml_str = MINIMAL_SUITE_TOML.replace("per_task = 3", "per_task = 5")
    config = _parse_suite_toml(toml_str)
    plan = plan_suite(config, templates)
    offsets = [p.seed_offset for p in plan.planned_instances]
    assert len(offsets) == len(set(offsets))


def test_plan_suite_coverage_warning_for_visibility() -> None:
    """If visibility target can't be met, a warning should be emitted."""
    templates = [
        _make_template_with_difficulty(
            "t1",
            "ground",
            {"easy": VisibilityLevel.ALL_GIVEN},
        ),
    ]
    toml_str = MINIMAL_SUITE_TOML.replace(
        "mix = {all_given = 1.0}",
        "mix = {all_given = 0.5, partial = 0.5}",
        1,  # only replace visibility mix
    )
    config = _parse_suite_toml(toml_str)
    plan = plan_suite(config, templates)
    vis_warnings = [w for w in plan.warnings if w.category == "visibility"]
    assert len(vis_warnings) > 0


def test_plan_suite_summary_counts() -> None:
    """Plan summary should have correct total and breakdowns."""
    templates = [
        _make_template_with_difficulty("t1", "ground", {"easy": VisibilityLevel.ALL_GIVEN}),
    ]
    config = _parse_suite_toml(MINIMAL_SUITE_TOML)
    plan = plan_suite(config, templates)
    assert plan.summary.total_instances == len(plan.planned_instances)
    assert plan.summary.by_discipline["ground"] == len(plan.planned_instances)


# --- Task 6: generate_instances + manifest ---


def test_load_suite_config_from_file(tmp_path: Path) -> None:
    """load_suite_config should read a TOML file and return SuiteConfig."""
    config_file = tmp_path / "suite.toml"
    config_file.write_text(MINIMAL_SUITE_TOML)
    config = load_suite_config(config_file)
    assert config.name == "test-suite"


def test_generate_instances_creates_instance_dirs(tmp_path: Path) -> None:
    """generate_instances should scaffold all instances and return a manifest."""
    from aec_bench.templates.registry import discover_templates

    templates, diagnostics = discover_templates()
    assert diagnostics == []
    assert len(templates) >= 1, "Need at least the Terzaghi built-in"

    toml_str = MINIMAL_SUITE_TOML.replace("per_task = 3", "per_task = 2")
    config = _parse_suite_toml(toml_str)
    config_with_output = config.model_copy(update={"output": OutputConfig(dir=tmp_path)})

    plan = plan_suite(config_with_output, templates)
    generated = generate_instances(plan, config_with_output)

    assert isinstance(generated.manifest, GenerationManifest)
    assert generated.output_root == tmp_path
    assert generated.manifest.suite_id == "test-suite"
    assert len(generated.task_paths) == plan.summary.total_instances

    # Verify instance directories exist on disk
    for instance_path in generated.task_paths:
        assert instance_path.exists(), f"Missing: {instance_path}"
        assert (instance_path / "task.toml").exists()

    reloaded = read_generated_task_set(tmp_path / "generation-manifest.json")
    tasks = load_generated_tasks(reloaded)
    assert [task.task_id for task in tasks] == [entry.task_id for entry in generated.manifest.instances]


def test_generate_instances_writes_one_generation_manifest(tmp_path: Path) -> None:
    """generate_instances writes deterministic replay data outside task directories."""
    from aec_bench.templates.registry import discover_templates

    templates, diagnostics = discover_templates()
    assert diagnostics == []
    toml_str = MINIMAL_SUITE_TOML.replace("per_task = 3", "per_task = 1")
    config = _parse_suite_toml(toml_str)
    config_with_output = config.model_copy(update={"output": OutputConfig(dir=tmp_path)})

    plan = plan_suite(config_with_output, templates)
    generate_instances(plan, config_with_output)

    manifest_path = tmp_path / "generation-manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["suite_id"] == "test-suite"
    assert data["schema_version"] == 1
    assert "created" not in data
    assert "framework_version" not in data
    assert "instances" in data
    assert not (tmp_path / "dataset.json").exists()
    assert not (tmp_path / "job.yaml").exists()
    config_data = json.loads((tmp_path / "generation-config.json").read_text())
    retained_replay_data = manifest_path.read_text() + json.dumps(config_data)
    assert str(tmp_path) not in retained_replay_data
    retained_keys = _nested_mapping_keys(data) | _nested_mapping_keys(config_data)
    forbidden_generation_keys = ("provider", "actor", "transport", "harbor")
    assert all(term not in key.lower() for key in retained_keys for term in forbidden_generation_keys)


def test_generate_instances_writes_unique_instance_paths(tmp_path: Path) -> None:
    """Suite execution should not collapse repeated template slots onto one path."""
    from aec_bench.templates.registry import discover_templates

    templates, diagnostics = discover_templates()
    assert diagnostics == []
    toml_str = MINIMAL_SUITE_TOML.replace("per_task = 3", "per_task = 5").replace(
        'include = ["*/*"]',
        'include = ["civil/mannings-pipe-capacity"]',
    )
    config = _parse_suite_toml(toml_str)
    config_with_output = config.model_copy(update={"output": OutputConfig(dir=tmp_path)})

    plan = plan_suite(config_with_output, templates)
    generated = generate_instances(plan, config_with_output)
    paths = [entry.task_id for entry in generated.manifest.instances]

    assert len(paths) == 5
    assert len(paths) == len(set(paths))


def test_manifest_instance_entries_keep_only_replay_inputs(tmp_path: Path) -> None:
    """Replay entries exclude sampled runtime content and provider settings."""
    from aec_bench.templates.registry import discover_templates

    templates, diagnostics = discover_templates()
    assert diagnostics == []
    toml_str = MINIMAL_SUITE_TOML.replace("per_task = 3", "per_task = 1")
    config = _parse_suite_toml(toml_str)
    config_with_output = config.model_copy(update={"output": OutputConfig(dir=tmp_path)})

    plan = plan_suite(config_with_output, templates)
    generated = generate_instances(plan, config_with_output)

    for entry in generated.manifest.instances:
        assert set(entry.model_dump(mode="json")) == {
            "task_id",
            "task_kind",
            "template_id",
            "seed",
            "instance_index",
            "difficulty",
            "tool_mode",
            "task_lifecycle",
            "task_visibility",
            "task_identity_id",
        }
