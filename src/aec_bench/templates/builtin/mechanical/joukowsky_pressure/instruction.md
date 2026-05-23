You are a senior mechanical engineer specializing in transient hydraulic analysis.

## Problem

Calculate the pressure rise from a rapid velocity change using the Joukowsky equation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Fluid density | {{ fluid_density_kg_m3 }} | kg/m3 |
| Pressure wave speed | {{ wave_speed_m_s }} | m/s |
| Velocity change | {{ velocity_change_m_s }} | m/s |

{% if archetype_description is defined %}
### Transient Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A Joukowsky pressure calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Pressure rise (Pa)
2. Pressure rise (kPa)
3. Equivalent pressure rise head (m)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use pressure rise = fluid density x wave speed x velocity change.
- Convert pressure rise from Pa to kPa by dividing by 1000.
- Use pressure head = pressure rise in Pa / (fluid density x 9.81).

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "pressure_rise_pa": <numeric_value>,
  "pressure_rise_kpa": <numeric_value>,
  "pressure_head_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
