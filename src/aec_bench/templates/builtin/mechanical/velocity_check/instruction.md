You are a senior mechanical engineer specializing in pipe hydraulic checks.

## Problem

Calculate pipe velocity from flow and diameter, then compare it with explicit minimum and maximum velocity criteria.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Flow rate | {{ flow_rate_l_s }} | L/s |
| Pipe internal diameter | {{ pipe_internal_diameter_mm }} | mm |
| Minimum velocity | {{ minimum_velocity_m_s }} | m/s |
| Maximum velocity | {{ maximum_velocity_m_s }} | m/s |

{% if archetype_description is defined %}
### Pipe Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A velocity check tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Pipe internal area
2. Flow velocity
3. Margin above minimum velocity
4. Margin below maximum velocity
5. Numeric pass flag, where 1 means velocity is within the explicit range

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use pipe area = pi x diameter squared / 4.
- Convert flow from L/s to m3/s before calculating velocity.
- Use only the explicit velocity criteria provided.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "pipe_area_m2": <numeric_value>,
  "velocity_m_s": <numeric_value>,
  "min_margin_m_s": <numeric_value>,
  "max_margin_m_s": <numeric_value>,
  "velocity_within_range": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

