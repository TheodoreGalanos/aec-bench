You are a senior mechanical engineer specializing in ventilation design.

## Problem

Calculate the room air change rate from the supplied outdoor or ventilation airflow.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Supply airflow | {{ supply_airflow_m3_h }} | m3/h |
| Room volume | {{ room_volume_m3 }} | m3 |

{% if archetype_description is defined %}
### Ventilation Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An air changes calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the air changes per hour (1/h).

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use air changes per hour = supply airflow / room volume.
- Keep units consistent: m3/h divided by m3 gives changes per hour.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answer in exactly this format:

```json
{
  "air_changes_per_h": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
