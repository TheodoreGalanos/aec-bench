# ABOUTME: Tests for template contract Pydantic models in aec_bench.templates.contracts.
# ABOUTME: Covers valid construction, rejection of bad inputs, and round-trip serialization.

import pytest
from pydantic import ValidationError

from aec_bench.templates.contracts import (
    DifficultyPreset,
    OutputSpec,
    ParamSpec,
    ParamType,
    TemplateConfig,
    TemplateMeta,
    ToolMode,
    VisibilityLevel,
)


def build_template_meta(**overrides: object) -> TemplateMeta:
    payload: dict[str, object] = {
        "name": "terzaghi-bearing-capacity",
        "description": "Compute ultimate bearing capacity using Terzaghi's equations.",
        "discipline": "Geotechnical",
        "category": "shallow-foundations",
        "standards": ["AS 4678-2002", "Terzaghi 1943"],
        "tags": ["au", "bearing-capacity", "shallow-foundations"],
        "tool_mode": ToolMode.WITH_TOOL,
    }
    payload.update(overrides)
    return TemplateMeta.model_validate(payload)


def build_param_spec_float(**overrides: object) -> ParamSpec:
    payload: dict[str, object] = {
        "type": ParamType.FLOAT,
        "description": "Cohesion of the soil",
        "unit": "kPa",
        "min_value": 0.0,
        "max_value": 200.0,
    }
    payload.update(overrides)
    return ParamSpec.model_validate(payload)


def build_param_spec_enum(**overrides: object) -> ParamSpec:
    payload: dict[str, object] = {
        "type": ParamType.ENUM,
        "description": "Foundation shape factor",
        "values": ["strip", "square", "circular"],
    }
    payload.update(overrides)
    return ParamSpec.model_validate(payload)


def build_output_spec(**overrides: object) -> OutputSpec:
    payload: dict[str, object] = {
        "description": "Ultimate bearing capacity in kPa",
    }
    payload.update(overrides)
    return OutputSpec.model_validate(payload)


def build_difficulty_preset(**overrides: object) -> DifficultyPreset:
    payload: dict[str, object] = {
        "description": "All parameters explicitly given",
        "visibility": VisibilityLevel.ALL_GIVEN,
        "archetypes": ["loose_sand", "medium_dense_sand"],
    }
    payload.update(overrides)
    return DifficultyPreset.model_validate(payload)


def build_template_config(**overrides: object) -> TemplateConfig:
    meta = build_template_meta()
    params: dict[str, object] = {
        "cohesion": {
            "type": ParamType.FLOAT,
            "description": "Soil cohesion",
            "unit": "kPa",
            "min_value": 0.0,
            "max_value": 200.0,
        },
        "foundation_shape": {
            "type": ParamType.ENUM,
            "description": "Foundation shape",
            "values": ["strip", "square", "circular"],
        },
    }
    outputs: dict[str, object] = {
        "q_ult": {
            "description": "Ultimate bearing capacity",
            "tolerance": 0.05,
        }
    }
    payload: dict[str, object] = {
        "meta": meta,
        "params": params,
        "outputs": outputs,
    }
    payload.update(overrides)
    return TemplateConfig.model_validate(payload)


# --- TemplateMeta tests ---


def test_template_meta_accepts_valid_payload() -> None:
    meta = build_template_meta()

    assert meta.name == "terzaghi-bearing-capacity"
    assert meta.discipline == "Geotechnical"
    assert meta.tool_mode is ToolMode.WITH_TOOL
    assert "AS 4678-2002" in meta.standards
    assert "au" in meta.tags


def test_template_meta_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        build_template_meta(name="   ")


def test_template_meta_rejects_blank_description() -> None:
    with pytest.raises(ValidationError):
        build_template_meta(description="")


def test_template_meta_rejects_blank_discipline() -> None:
    with pytest.raises(ValidationError):
        build_template_meta(discipline="   ")


def test_template_meta_rejects_blank_category() -> None:
    with pytest.raises(ValidationError):
        build_template_meta(category="")


def test_template_meta_roundtrip() -> None:
    original = build_template_meta()

    serialized = original.model_dump(mode="json")
    restored = TemplateMeta.model_validate(serialized)

    assert restored == original
    assert restored.tool_mode is ToolMode.WITH_TOOL


# --- ParamSpec tests ---


def test_param_spec_accepts_float_param() -> None:
    param = build_param_spec_float()

    assert param.type is ParamType.FLOAT
    assert param.min_value == 0.0
    assert param.max_value == 200.0
    assert param.unit == "kPa"


def test_param_spec_accepts_enum_param() -> None:
    param = build_param_spec_enum()

    assert param.type is ParamType.ENUM
    assert "strip" in param.values  # type: ignore[operator]


def test_param_spec_accepts_int_param() -> None:
    param = ParamSpec.model_validate(
        {
            "type": ParamType.INT,
            "description": "Number of layers",
            "min_value": 1.0,
            "max_value": 10.0,
        }
    )

    assert param.type is ParamType.INT


def test_param_spec_rejects_float_without_range() -> None:
    with pytest.raises(ValidationError):
        ParamSpec.model_validate(
            {
                "type": ParamType.FLOAT,
                "description": "Cohesion",
            }
        )


def test_param_spec_rejects_float_with_only_min() -> None:
    with pytest.raises(ValidationError):
        ParamSpec.model_validate(
            {
                "type": ParamType.FLOAT,
                "description": "Cohesion",
                "min_value": 0.0,
            }
        )


def test_param_spec_rejects_enum_without_values() -> None:
    with pytest.raises(ValidationError):
        ParamSpec.model_validate(
            {
                "type": ParamType.ENUM,
                "description": "Foundation shape",
            }
        )


def test_param_spec_optional_flag_defaults_false() -> None:
    param = build_param_spec_float()

    assert param.optional is False


def test_param_spec_optional_flag_can_be_set() -> None:
    param = build_param_spec_float(optional=True)

    assert param.optional is True


# --- OutputSpec tests ---


def test_output_spec_accepts_valid_payload() -> None:
    spec = build_output_spec()

    assert spec.description == "Ultimate bearing capacity in kPa"


def test_output_spec_default_tolerance() -> None:
    spec = build_output_spec()

    assert spec.tolerance == pytest.approx(0.03)


def test_output_spec_custom_tolerance() -> None:
    spec = build_output_spec(tolerance=0.05)

    assert spec.tolerance == pytest.approx(0.05)


def test_output_spec_rejects_blank_description() -> None:
    with pytest.raises(ValidationError):
        build_output_spec(description="   ")


# --- DifficultyPreset tests ---


def test_difficulty_preset_accepts_valid_payload() -> None:
    preset = build_difficulty_preset()

    assert preset.visibility is VisibilityLevel.ALL_GIVEN
    assert "loose_sand" in preset.archetypes
    assert preset.hidden_params == []


def test_difficulty_preset_partial_requires_hidden_params() -> None:
    with pytest.raises(ValidationError):
        build_difficulty_preset(
            visibility=VisibilityLevel.PARTIAL,
            hidden_params=[],
        )


def test_difficulty_preset_partial_with_hidden_params_is_valid() -> None:
    preset = build_difficulty_preset(
        visibility=VisibilityLevel.PARTIAL,
        hidden_params=["cohesion"],
    )

    assert preset.visibility is VisibilityLevel.PARTIAL
    assert "cohesion" in preset.hidden_params


def test_difficulty_preset_scenario_only_no_hidden_params_required() -> None:
    preset = build_difficulty_preset(
        visibility=VisibilityLevel.SCENARIO_ONLY,
        hidden_params=[],
    )

    assert preset.visibility is VisibilityLevel.SCENARIO_ONLY


def test_difficulty_preset_extra_dict_defaults_empty() -> None:
    preset = build_difficulty_preset()

    assert preset.extra == {}


# --- TemplateConfig tests ---


def test_template_config_accepts_valid_payload() -> None:
    config = build_template_config()

    assert config.meta.name == "terzaghi-bearing-capacity"
    assert "cohesion" in config.params
    assert "q_ult" in config.outputs


def test_template_config_roundtrip() -> None:
    original = build_template_config()

    serialized = original.model_dump(mode="json")
    restored = TemplateConfig.model_validate(serialized)

    assert restored == original
    assert restored.meta.discipline == "Geotechnical"
    assert restored.params["cohesion"].type is ParamType.FLOAT
    assert restored.outputs["q_ult"].tolerance == pytest.approx(0.05)


def test_template_config_empty_optional_collections() -> None:
    config = build_template_config()

    assert config.archetypes == {}
    assert config.difficulty == {}
    assert config.constraints == []


def test_template_config_with_archetypes() -> None:
    archetype_data = {
        "loose_sand": {
            "description": "Loose sandy soil",
            "site_contexts": ["coastal", "riverbank"],
            "params": {
                "cohesion": {"min": 0.0, "max": 5.0},
                "friction_angle": {"min": 28.0, "max": 32.0},
            },
        }
    }
    config = build_template_config(archetypes=archetype_data)

    assert "loose_sand" in config.archetypes
    assert config.archetypes["loose_sand"].description == "Loose sandy soil"


def test_template_config_with_difficulty_presets() -> None:
    difficulty_data = {
        "easy": {
            "description": "All values given directly",
            "visibility": "all_given",
            "archetypes": ["loose_sand"],
        },
        "hard": {
            "description": "Must infer soil params from site context",
            "visibility": "partial",
            "archetypes": ["loose_sand"],
            "hidden_params": ["cohesion"],
        },
    }
    config = build_template_config(difficulty=difficulty_data)

    assert "easy" in config.difficulty
    assert "hard" in config.difficulty
    assert config.difficulty["hard"].visibility is VisibilityLevel.PARTIAL
