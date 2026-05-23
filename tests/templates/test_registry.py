# ABOUTME: Tests for the template registry module that loads, discovers, and validates templates.
# ABOUTME: Uses tmp_path fixtures to create minimal template directories for isolated testing.

from pathlib import Path
from types import ModuleType

import pytest

from aec_bench.templates.registry import (
    discover_templates,
    has_custom_verifier,
    load_engine_module,
    load_template,
    validate_template,
)

TRIVIAL_ENGINE = """
def compute(value_a: float = 0.0) -> dict[str, float]:
    return {"result": value_a * 2}
"""

MINIMAL_TOML = """
[meta]
name = "test-template"
description = "A test"
discipline = "test"
category = "test-cat"
standards = []
tags = []
tool_mode = "with-tool"

[params.value_a]
type = "float"
description = "Input A"
min = 0.0
max = 100.0

[outputs.result]
description = "The result"
"""


def _make_template(
    tmp_path: Path,
    *,
    engine_code: str = TRIVIAL_ENGINE,
    toml_str: str = MINIMAL_TOML,
    instruction: str = "Compute the result.",
) -> Path:
    """Build a minimal template directory for testing."""
    tdir = tmp_path / "my_template"
    tdir.mkdir()
    (tdir / "engine.py").write_text(engine_code)
    (tdir / "params.toml").write_text(toml_str)
    (tdir / "instruction.md").write_text(instruction)
    return tdir


# --- load_template tests ---


def test_load_template_from_valid_directory(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)

    config, path = load_template(tdir)

    assert config.meta.name == "test-template"
    assert config.meta.discipline == "test"
    assert config.meta.category == "test-cat"
    assert path == tdir
    assert "value_a" in config.params
    assert "result" in config.outputs


def test_load_template_returns_param_with_remapped_range(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)

    config, _ = load_template(tdir)

    param = config.params["value_a"]
    assert param.min_value == 0.0
    assert param.max_value == 100.0


def test_load_template_rejects_missing_engine(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)
    (tdir / "engine.py").unlink()

    with pytest.raises((FileNotFoundError, ValueError)):
        load_template(tdir)


def test_load_template_rejects_missing_params(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)
    (tdir / "params.toml").unlink()

    with pytest.raises((FileNotFoundError, ValueError)):
        load_template(tdir)


def test_load_template_rejects_engine_without_compute(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path, engine_code="x = 42  # no compute function")

    with pytest.raises((AttributeError, ValueError)):
        load_template(tdir)


def test_load_template_with_archetypes(tmp_path: Path) -> None:
    toml_with_archetypes = (
        MINIMAL_TOML
        + """
[archetypes.soft_nc_clay]
description = "Soft normally consolidated clay"
cohesion_kpa = {min = 5, max = 15}
friction_angle_deg = {min = 0, max = 5}
site_contexts = ["brisbane-alluvial"]
"""
    )
    tdir = _make_template(tmp_path, toml_str=toml_with_archetypes)

    config, _ = load_template(tdir)

    assert "soft_nc_clay" in config.archetypes
    archetype = config.archetypes["soft_nc_clay"]
    assert archetype.description == "Soft normally consolidated clay"
    assert "cohesion_kpa" in archetype.params
    assert archetype.params["cohesion_kpa"].min == 5
    assert archetype.params["cohesion_kpa"].max == 15
    assert "brisbane-alluvial" in archetype.site_contexts


def test_load_template_with_difficulty_presets(tmp_path: Path) -> None:
    toml_with_difficulty = (
        MINIMAL_TOML
        + """
[archetypes.loose_sand]
description = "Loose sandy soil"
site_contexts = ["coastal"]
friction_deg = {min = 28, max = 32}

[difficulty.easy]
description = "All values given directly"
visibility = "all_given"
archetypes = ["loose_sand"]

[difficulty.hard]
description = "Must infer from context"
visibility = "partial"
archetypes = ["loose_sand"]
hidden_params = ["value_a"]
"""
    )
    tdir = _make_template(tmp_path, toml_str=toml_with_difficulty)

    config, _ = load_template(tdir)

    assert "easy" in config.difficulty
    assert "hard" in config.difficulty
    assert config.difficulty["hard"].hidden_params == ["value_a"]


def test_load_template_difficulty_extra_fields_captured(tmp_path: Path) -> None:
    toml_with_extra = (
        MINIMAL_TOML
        + """
[archetypes.loose_sand]
description = "Loose sandy soil"
site_contexts = ["coastal"]
friction_deg = {min = 28, max = 32}

[difficulty.medium]
description = "Medium difficulty"
visibility = "all_given"
archetypes = ["loose_sand"]
custom_key = "custom_value"
"""
    )
    tdir = _make_template(tmp_path, toml_str=toml_with_extra)

    config, _ = load_template(tdir)

    assert "medium" in config.difficulty
    assert config.difficulty["medium"].extra.get("custom_key") == "custom_value"


# --- load_engine_module tests ---


def test_load_engine_module_returns_callable(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)

    module = load_engine_module(tdir)

    assert isinstance(module, ModuleType)
    assert callable(module.compute)


def test_load_engine_module_rejects_engine_without_compute(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path, engine_code="x = 42")

    with pytest.raises((AttributeError, ValueError)):
        load_engine_module(tdir)


def test_load_engine_module_raises_on_missing_file(tmp_path: Path) -> None:
    tdir = tmp_path / "no_engine"
    tdir.mkdir()

    with pytest.raises((FileNotFoundError, ValueError)):
        load_engine_module(tdir)


# --- discover_templates tests ---


def _count_builtin_templates() -> int:
    """Count built-in templates so tests can account for them in discovery assertions."""
    return len(discover_templates(user_dirs=[]))


def test_discover_templates_from_user_dir(tmp_path: Path) -> None:
    user_dir = tmp_path / "user_templates"
    user_dir.mkdir()
    tdir = user_dir / "my_template"
    tdir.mkdir()
    (tdir / "engine.py").write_text(TRIVIAL_ENGINE)
    (tdir / "params.toml").write_text(MINIMAL_TOML)
    (tdir / "instruction.md").write_text("Compute the result.")

    builtin_count = _count_builtin_templates()
    results = discover_templates(user_dirs=[user_dir])

    assert len(results) == builtin_count + 1
    user_results = [(c, p) for c, p in results if p == tdir]
    assert len(user_results) == 1
    assert user_results[0][0].meta.name == "test-template"


def test_discover_templates_empty_when_no_dirs(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    builtin_count = _count_builtin_templates()
    results = discover_templates(user_dirs=[empty_dir])

    assert len(results) == builtin_count


def test_discover_templates_multiple_user_dirs(tmp_path: Path) -> None:
    dir_a = tmp_path / "dir_a"
    dir_a.mkdir()
    dir_b = tmp_path / "dir_b"
    dir_b.mkdir()

    # Template in dir_a
    tdir_a = dir_a / "tmpl_a"
    tdir_a.mkdir()
    (tdir_a / "engine.py").write_text(TRIVIAL_ENGINE)
    (tdir_a / "params.toml").write_text(MINIMAL_TOML)
    (tdir_a / "instruction.md").write_text("A")

    # Template in dir_b
    tdir_b = dir_b / "tmpl_b"
    tdir_b.mkdir()
    (tdir_b / "engine.py").write_text(TRIVIAL_ENGINE)
    (tdir_b / "params.toml").write_text(MINIMAL_TOML)
    (tdir_b / "instruction.md").write_text("B")

    builtin_count = _count_builtin_templates()
    results = discover_templates(user_dirs=[dir_a, dir_b])

    assert len(results) == builtin_count + 2


def test_discover_templates_finds_nested_templates(tmp_path: Path) -> None:
    user_dir = tmp_path / "user_templates"
    user_dir.mkdir()
    # Template nested two levels deep: user_dir/domain/task_name/engine.py
    nested = user_dir / "ground" / "bearing_capacity"
    nested.mkdir(parents=True)
    (nested / "engine.py").write_text(TRIVIAL_ENGINE)
    (nested / "params.toml").write_text(MINIMAL_TOML)
    (nested / "instruction.md").write_text("Nested template.")

    builtin_count = _count_builtin_templates()
    results = discover_templates(user_dirs=[user_dir])

    assert len(results) == builtin_count + 1
    user_results = [(c, p) for c, p in results if p == nested]
    assert len(user_results) == 1
    assert user_results[0][0].meta.name == "test-template"


def test_discover_templates_skips_directories_without_engine(tmp_path: Path) -> None:
    user_dir = tmp_path / "mixed_dir"
    user_dir.mkdir()

    # Valid template
    valid = user_dir / "valid_tmpl"
    valid.mkdir()
    (valid / "engine.py").write_text(TRIVIAL_ENGINE)
    (valid / "params.toml").write_text(MINIMAL_TOML)
    (valid / "instruction.md").write_text("Valid")

    # Directory without engine.py — should be skipped
    invalid = user_dir / "no_engine_tmpl"
    invalid.mkdir()
    (invalid / "params.toml").write_text(MINIMAL_TOML)
    (invalid / "instruction.md").write_text("Invalid")

    builtin_count = _count_builtin_templates()
    results = discover_templates(user_dirs=[user_dir])

    assert len(results) == builtin_count + 1
    user_results = [(c, p) for c, p in results if p == valid]
    assert len(user_results) == 1


# --- has_custom_verifier tests ---


def test_has_custom_verifier_true(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)
    (tdir / "verify.py").write_text("def verify(): pass")

    assert has_custom_verifier(tdir) is True


def test_has_custom_verifier_false(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)

    assert has_custom_verifier(tdir) is False


# --- validate_template tests ---


def test_validate_template_returns_empty_for_valid(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)

    errors = validate_template(tdir)

    assert errors == []


def test_validate_template_returns_errors_for_missing_engine(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)
    (tdir / "engine.py").unlink()

    errors = validate_template(tdir)

    assert len(errors) > 0
    assert any("engine" in e.lower() or "engine.py" in e.lower() for e in errors)


def test_validate_template_returns_errors_for_missing_params(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)
    (tdir / "params.toml").unlink()

    errors = validate_template(tdir)

    assert len(errors) > 0


def test_validate_template_returns_errors_for_missing_instruction(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path)
    (tdir / "instruction.md").unlink()

    errors = validate_template(tdir)

    assert len(errors) > 0


def test_validate_template_returns_errors_for_engine_without_compute(tmp_path: Path) -> None:
    tdir = _make_template(tmp_path, engine_code="x = 42  # no compute")

    errors = validate_template(tdir)

    assert len(errors) > 0
    assert any("compute" in e.lower() for e in errors)
