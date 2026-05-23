# ABOUTME: Tests for the Jinja2 instruction renderer that renders templates with sampled param values.
# ABOUTME: Covers visible/hidden param separation, tool section toggling, outputs, and standards.

from datetime import UTC, datetime

from aec_bench.generation.contracts import GenerationMetadata, SampledInstance
from aec_bench.generation.instruction_renderer import render_instruction
from aec_bench.templates.contracts import (
    OutputSpec,
    ParamSpec,
    ParamType,
    TemplateConfig,
    TemplateMeta,
    ToolMode,
    VisibilityLevel,
)

TEST_TEMPLATE = """You are an engineer.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
{% for param in visible_params %}| {{ param.description }} | {{ param.value }} | {{ param.unit or '-' }} |
{% endfor %}
{% if tool_mode == "with-tool" %}
## Tool

A tool is available at `/workspace/calc.py`.
{% endif %}

## Required

{% for output in outputs %}{{ loop.index }}. {{ output.description }}
{% endfor %}

## Standards

{% for std in standards %}- {{ std }}
{% endfor %}"""


def _build_test_instance() -> SampledInstance:
    return SampledInstance(
        instance_name="test-01",
        all_params={"value_a": 5.0, "mode": "fast"},
        visible_params={"value_a": 5.0},
        hidden_params={"mode": "fast"},
        ground_truth={"result": 10.0},
        archetype_name="test_arch",
        site_context="test-site",
        difficulty="easy",
        metadata=GenerationMetadata(
            template="test",
            seed=42,
            timestamp=datetime.now(UTC),
            difficulty="easy",
            visibility_level=VisibilityLevel.ALL_GIVEN,
            archetype="test_arch",
            site_context="test-site",
        ),
    )


def _build_test_config(tool_mode: ToolMode = ToolMode.WITH_TOOL) -> TemplateConfig:
    return TemplateConfig(
        meta=TemplateMeta(
            name="test",
            description="test",
            discipline="test",
            category="test",
            standards=["AS 1234"],
            tags=[],
            tool_mode=tool_mode,
        ),
        params={
            "value_a": ParamSpec(
                type=ParamType.FLOAT,
                description="Input A",
                unit="m",
                min_value=0.0,
                max_value=100.0,
            ),
            "mode": ParamSpec(
                type=ParamType.ENUM,
                description="Mode",
                values=["fast", "slow"],
            ),
        },
        outputs={"result": OutputSpec(description="The result")},
    )


def test_render_instruction_substitutes_visible_params() -> None:
    instance = _build_test_instance()
    config = _build_test_config()

    result = render_instruction(TEST_TEMPLATE, instance, config)

    assert "5.0" in result


def test_render_instruction_hides_hidden_params() -> None:
    instance = _build_test_instance()
    config = _build_test_config()

    result = render_instruction(TEST_TEMPLATE, instance, config)

    # "mode" is a hidden param — it should NOT appear in the visible_params table rows
    # The table row for "Mode" should not be present (the description for "mode" param)
    assert "Mode" not in result


def test_render_instruction_includes_tool_section() -> None:
    instance = _build_test_instance()
    config = _build_test_config(tool_mode=ToolMode.WITH_TOOL)

    result = render_instruction(TEST_TEMPLATE, instance, config)

    assert "tool is available" in result


def test_render_instruction_excludes_tool_section() -> None:
    instance = _build_test_instance()
    config = _build_test_config(tool_mode=ToolMode.NO_TOOL)

    result = render_instruction(TEST_TEMPLATE, instance, config)

    assert "tool is available" not in result


def test_render_instruction_includes_outputs() -> None:
    instance = _build_test_instance()
    config = _build_test_config()

    result = render_instruction(TEST_TEMPLATE, instance, config)

    assert "The result" in result


def test_render_instruction_includes_standards() -> None:
    instance = _build_test_instance()
    config = _build_test_config()

    result = render_instruction(TEST_TEMPLATE, instance, config)

    assert "AS 1234" in result


# Template that uses {% if param is defined %} guards for conditional sections
_CONDITIONAL_TEMPLATE = """## Given

| Parameter | Value |
|-----------|-------|
| Input A | {{ value_a }} |
{% if mode is defined %}| Mode | {{ mode }} |
{% endif %}

{% if mode is defined %}
## Mode Details

Running in {{ mode }} mode.
{% endif %}
"""


def test_hidden_params_not_accessible_via_direct_access() -> None:
    """Hidden params must not be in the Jinja2 context for direct access.

    Templates use {% if param is defined %} guards to conditionally show
    sections. Hidden params must make these guards evaluate to False.
    """
    instance = _build_test_instance()
    config = _build_test_config()

    result = render_instruction(_CONDITIONAL_TEMPLATE, instance, config)

    # "mode" is hidden — {% if mode is defined %} should be False
    assert "Mode Details" not in result
    assert "fast" not in result
    # visible param "value_a" should still be accessible
    assert "5.0" in result


def test_visible_params_accessible_via_direct_access() -> None:
    """Visible params must be in the Jinja2 context for direct access."""
    instance = SampledInstance(
        instance_name="test-01",
        all_params={"value_a": 5.0, "mode": "fast"},
        visible_params={"value_a": 5.0, "mode": "fast"},
        hidden_params={},
        ground_truth={"result": 10.0},
        archetype_name="test_arch",
        site_context="test-site",
        difficulty="easy",
        metadata=GenerationMetadata(
            template="test",
            seed=42,
            timestamp=datetime.now(UTC),
            difficulty="easy",
            visibility_level=VisibilityLevel.ALL_GIVEN,
            archetype="test_arch",
            site_context="test-site",
        ),
    )
    config = _build_test_config()

    result = render_instruction(_CONDITIONAL_TEMPLATE, instance, config)

    # Both params are visible — both should appear
    assert "Mode Details" in result
    assert "fast" in result
    assert "5.0" in result
