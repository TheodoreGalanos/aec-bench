You are a senior mechanical engineer specializing in pump hydraulics.

## Problem

Calculate the total dynamic head required for a pump installation and the corresponding hydraulic power.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Flow rate | {{ flow_rate_m3_h }} | m3/h |
| Suction pressure | {{ suction_pressure_kpa }} | kPa |
| Discharge pressure | {{ discharge_pressure_kpa }} | kPa |
| Elevation difference | {{ elevation_difference_m }} | m |
| Pipe friction losses | {{ pipe_friction_losses_kpa }} | kPa |
| Fluid density | {{ fluid_density_kg_m3 }} | kg/m3 |

{% if archetype_description is defined %}
### Pump Duty Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A pump head calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Static elevation head (m)
2. Pressure head differential (m)
3. Friction loss head (m)
4. Total dynamic head (m)
5. Hydraulic power (kW)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use g = 9.81 m/s2.
- Convert flow from m3/h to m3/s by dividing by 3600.
- Convert pressure difference to head using head = delta pressure x 1000 / (density x g).
- Convert pipe losses to head using the same pressure-to-head relationship.
- Use total dynamic head = static head + pressure head differential + friction head.
- Use hydraulic power = density x g x flow x total dynamic head / 1000.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "static_head_m": <numeric_value>,
  "pressure_head_differential_m": <numeric_value>,
  "friction_head_m": <numeric_value>,
  "total_dynamic_head_m": <numeric_value>,
  "hydraulic_power_kw": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
