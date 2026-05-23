You are a senior mechanical engineer specializing in pump hydraulics.

## Problem

Calculate Net Positive Suction Head Available at a pump inlet and compare it with the pump NPSH required.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Suction vessel pressure | {{ suction_vessel_pressure_kpa_abs }} | kPa abs |
| Liquid level above pump centreline | {{ liquid_level_above_pump_m }} | m |
| Suction pipe losses | {{ suction_pipe_losses_kpa }} | kPa |
| Fluid vapor pressure | {{ vapor_pressure_kpa_abs }} | kPa abs |
| Fluid density | {{ fluid_density_kg_m3 }} | kg/m3 |
| NPSH required | {{ npsh_required_m }} | m |

{% if archetype_description is defined %}
### Pump Suction Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An NPSH calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Suction pressure head (m)
2. Vapor pressure head (m)
3. Suction loss head (m)
4. NPSH available (m)
5. Cavitation margin (m)
6. Margin ratio NPSHa/NPSHr

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use g = 9.81 m/s2.
- Convert pressure in kPa to head in metres of fluid using head = pressure x 1000 / (density x g).
- Use NPSHa = pressure head + static level - vapor pressure head - loss head.
- Use cavitation margin = NPSHa - NPSH required.
- Use margin ratio = NPSHa / NPSH required.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "pressure_head_m": <numeric_value>,
  "vapor_pressure_head_m": <numeric_value>,
  "loss_head_m": <numeric_value>,
  "npsh_available_m": <numeric_value>,
  "cavitation_margin_m": <numeric_value>,
  "margin_ratio": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
