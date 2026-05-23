You are a senior mechanical engineer specializing in pipe hydraulics.

## Problem

Calculate total minor head loss for a pipe run using explicit fitting K factors.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Fitting 1 K factor | {{ fitting_1_k }} | - |
| Fitting 1 quantity | {{ fitting_1_quantity }} | - |
| Fitting 2 K factor | {{ fitting_2_k }} | - |
| Fitting 2 quantity | {{ fitting_2_quantity }} | - |
| Fitting 3 K factor | {{ fitting_3_k }} | - |
| Fitting 3 quantity | {{ fitting_3_quantity }} | - |
| Flow velocity | {{ flow_velocity_m_s }} | m/s |
| Pipe diameter | {{ pipe_diameter_mm }} | mm |
| Darcy friction factor | {{ darcy_friction_factor }} | - |

{% if archetype_description is defined %}
### Pipework Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A minor losses calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Total K factor
2. Velocity head in metres
3. Total minor head loss in metres
4. Equivalent pipe length in metres using the supplied Darcy friction factor

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use total K = sum of each fitting K factor multiplied by its quantity.
- Use velocity head = velocity squared / (2g), with g = 9.81 m/s2.
- Use total minor loss = total K x velocity head.
- Use equivalent length = total minor loss x pipe diameter / (Darcy friction factor x velocity head).

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "total_k": <numeric_value>,
  "velocity_head_m": <numeric_value>,
  "total_minor_loss_m": <numeric_value>,
  "equivalent_length_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

