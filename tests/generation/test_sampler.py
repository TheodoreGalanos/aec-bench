# ABOUTME: Tests for the generation sampler — sample_instance() and associated contracts.
# ABOUTME: Follows TDD: written before implementation, covers contracts and sampling behaviour.

from aec_bench.generation.contracts import GenerationMetadata, SampledInstance
from aec_bench.generation.sampler import sample_instance
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


def _trivial_compute(value_a: float = 0.0, mode: str = "normal") -> dict[str, float]:
    """Minimal engine compute function for testing."""
    return {"result": value_a * 2}


def _build_test_config() -> TemplateConfig:
    """Build a minimal TemplateConfig with one float param, one enum param, one archetype."""
    meta = TemplateMeta.model_validate(
        {
            "name": "test-template",
            "description": "A template for testing the sampler",
            "discipline": "Geotechnical",
            "category": "shallow-foundations",
            "tool_mode": ToolMode.WITH_TOOL,
        }
    )

    params = {
        "value_a": ParamSpec.model_validate(
            {
                "type": ParamType.FLOAT,
                "description": "Primary float parameter",
                "unit": "kPa",
                "min_value": 0.0,
                "max_value": 100.0,
            }
        ),
        "mode": ParamSpec.model_validate(
            {
                "type": ParamType.ENUM,
                "description": "Operating mode",
                "values": ["normal", "fast", "accurate"],
            }
        ),
    }

    outputs = {
        "result": OutputSpec.model_validate(
            {
                "description": "Computed result",
                "tolerance": 0.05,
            }
        )
    }

    archetypes = {
        "test-archetype": ArchetypeSpec.model_validate(
            {
                "description": "A test archetype",
                "site_contexts": ["perth-coastal", "sydney-hawkesbury"],
                "params": {
                    "value_a": ArchetypeRange(min=10.0, max=50.0),
                },
            }
        )
    }

    difficulty = {
        "easy": DifficultyPreset.model_validate(
            {
                "description": "All parameters explicitly given",
                "visibility": VisibilityLevel.ALL_GIVEN,
                "archetypes": ["test-archetype"],
            }
        ),
        "hard": DifficultyPreset.model_validate(
            {
                "description": "Some parameters hidden",
                "visibility": VisibilityLevel.PARTIAL,
                "archetypes": ["test-archetype"],
                "hidden_params": ["value_a"],
            }
        ),
    }

    return TemplateConfig.model_validate(
        {
            "meta": meta,
            "params": params,
            "outputs": outputs,
            "archetypes": archetypes,
            "difficulty": difficulty,
        }
    )


# --- Contract shape tests ---


def test_sampled_instance_has_all_params() -> None:
    """All declared params must be present in all_params."""
    config = _build_test_config()
    result = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="easy",
        seed=42,
        instance_index=0,
    )

    assert isinstance(result, SampledInstance)
    assert "value_a" in result.all_params
    assert "mode" in result.all_params


def test_sampled_instance_respects_archetype_ranges() -> None:
    """Float param with archetype override must fall within the archetype's range."""
    config = _build_test_config()
    result = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="easy",
        seed=99,
        instance_index=0,
    )

    value_a = result.all_params["value_a"]
    assert isinstance(value_a, float)
    # test-archetype defines value_a in [10.0, 50.0]
    assert 10.0 <= value_a <= 50.0


def test_sampled_instance_visibility_all_given() -> None:
    """Easy difficulty (ALL_GIVEN) should expose all params as visible, none hidden."""
    config = _build_test_config()
    result = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="easy",
        seed=7,
        instance_index=0,
    )

    assert set(result.visible_params.keys()) == set(result.all_params.keys())
    assert result.hidden_params == {}


def test_sampled_instance_visibility_partial() -> None:
    """Hard difficulty (PARTIAL) should move hidden_params to hidden_params dict."""
    config = _build_test_config()
    result = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="hard",
        seed=7,
        instance_index=0,
    )

    assert "value_a" in result.hidden_params
    assert "value_a" not in result.visible_params
    # mode is not in hidden_params list, so it should be visible
    assert "mode" in result.visible_params


def test_sampled_instance_deterministic_with_seed() -> None:
    """Same seed + index + difficulty must produce an identical SampledInstance."""
    config = _build_test_config()
    result_a = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="easy",
        seed=123,
        instance_index=5,
    )
    result_b = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="easy",
        seed=123,
        instance_index=5,
    )

    assert result_a.all_params == result_b.all_params
    assert result_a.instance_name == result_b.instance_name
    assert result_a.ground_truth == result_b.ground_truth


def test_sampled_instance_different_seeds_differ() -> None:
    """Different seeds must (almost always) produce different float param values."""
    config = _build_test_config()
    result_a = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="easy",
        seed=1,
        instance_index=0,
    )
    result_b = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="easy",
        seed=99999,
        instance_index=0,
    )

    # With different seeds, the float param should differ (not 100% guaranteed
    # but extremely likely given the large range)
    assert result_a.all_params["value_a"] != result_b.all_params["value_a"]


def test_sampled_instance_has_ground_truth() -> None:
    """ground_truth must contain float values from engine_compute."""
    config = _build_test_config()
    result = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="easy",
        seed=42,
        instance_index=0,
    )

    assert "result" in result.ground_truth
    assert isinstance(result.ground_truth["result"], float)
    # _trivial_compute returns value_a * 2
    expected = float(result.all_params["value_a"]) * 2
    assert result.ground_truth["result"] == expected


def test_sampled_instance_has_site_context() -> None:
    """site_context must be a non-empty string."""
    config = _build_test_config()
    result = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="easy",
        seed=42,
        instance_index=0,
    )

    assert isinstance(result.site_context, str)
    assert len(result.site_context) > 0


def test_sampled_instance_has_valid_metadata() -> None:
    """Metadata must have origin=='generated' and template matching config name."""
    config = _build_test_config()
    result = sample_instance(
        config=config,
        engine_compute=_trivial_compute,
        difficulty_name="easy",
        seed=42,
        instance_index=0,
    )

    assert isinstance(result.metadata, GenerationMetadata)
    assert result.metadata.origin == "generated"
    assert result.metadata.template == "test-template"
