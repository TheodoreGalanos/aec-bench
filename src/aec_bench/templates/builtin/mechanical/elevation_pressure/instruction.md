You are a senior mechanical engineer specializing in hydraulic systems.

## Problem

Calculate static pressure change caused by an elevation difference in a fluid system.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Fluid density | {{ fluid_density_kg_m3 }} | kg/m3 |
| Elevation change | {{ elevation_change_m }} | m |

{% if archetype_description is defined %}
### Hydraulic Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An elevation pressure calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Elevation head in metres
2. Static pressure change in kPa
3. Static pressure change in bar

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use g = 9.81 m/s2.
- Use pressure change = fluid density x g x elevation change.
- Preserve the sign of elevation change.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "elevation_head_m": <numeric_value>,
  "pressure_change_kpa": <numeric_value>,
  "pressure_change_bar": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

