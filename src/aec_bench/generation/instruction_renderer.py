# ABOUTME: Renders Jinja2 instruction templates with concrete parameter values from a sampled instance.  # noqa: E501
# ABOUTME: Builds template context from visible params, outputs, standards, and tool mode.

from jinja2 import BaseLoader, Environment

from aec_bench.generation.contracts import SampledInstance
from aec_bench.templates.contracts import TemplateConfig, ToolMode


def _format_value(value: float | int | str) -> str:
    """Round floats to 2 decimal places for human-readable instructions."""
    if isinstance(value, float):
        return str(round(value, 2))
    return str(value)


def render_instruction(
    template_str: str,
    instance: SampledInstance,
    config: TemplateConfig,
) -> str:
    """Render a Jinja2 instruction template with values from a sampled instance.

    Builds context from the instance's visible parameters and the template config,
    then renders the template string and returns the result.
    """
    visible_params = [
        {
            "name": param_name,
            "value": _format_value(instance.visible_params[param_name]),
            "unit": config.params[param_name].unit,
            "description": config.params[param_name].description,
        }
        for param_name in instance.visible_params
        if param_name in config.params
    ]

    outputs = [
        {
            "name": output_name,
            "description": spec.description,
        }
        for output_name, spec in config.outputs.items()
    ]

    # Resolve the archetype's human-readable description from the config
    archetype_description = instance.archetype_name
    if instance.archetype_name in config.archetypes:
        archetype_description = config.archetypes[instance.archetype_name].description

    tool_mode_str = str(config.meta.tool_mode)
    tool_available = config.meta.tool_mode in {ToolMode.WITH_TOOL, ToolMode.BOTH}

    context: dict[str, object] = {
        "visible_params": visible_params,
        "outputs": outputs,
        "standards": config.meta.standards,
        "tool_mode": tool_mode_str,
        "tool_available": tool_available,
        "archetype": {
            "description": archetype_description,
            "site_context": instance.site_context,
        },
        "archetype_description": archetype_description,
        "site_context": instance.site_context,
        "meta": config.meta.model_dump(),
    }

    # Expose visible param values for direct template access (e.g., {{ footing_shape }}).
    # Only visible params are injected so that {% if param is defined %} guards
    # correctly exclude hidden params at hard difficulty.
    context.update({k: _format_value(v) for k, v in instance.visible_params.items()})

    env = Environment(loader=BaseLoader())
    template = env.from_string(template_str)
    return template.render(**context)
