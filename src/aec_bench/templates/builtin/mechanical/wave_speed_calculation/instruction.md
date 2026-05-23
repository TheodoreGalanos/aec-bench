You are a senior mechanical engineer specializing in hydraulic transients.

## Problem

Calculate pressure wave propagation speed in a pipe, accounting for both fluid compressibility and pipe-wall flexibility.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Fluid bulk modulus K | {{ fluid_bulk_modulus_gpa }} | GPa |
| Fluid density rho | {{ fluid_density_kg_m3 }} | kg/m3 |
| Pipe elastic modulus E | {{ pipe_elastic_modulus_gpa }} | GPa |
| Pipe internal diameter D | {{ pipe_diameter_mm }} | mm |
| Pipe wall thickness e | {{ pipe_wall_thickness_mm }} | mm |
| Restraint condition | {{ restraint_condition }} | - |

{% if archetype_description is defined %}
### Pipe Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A wave speed calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Fluid-only wave speed (m/s)
2. Pipe flexibility factor
3. Pressure wave speed in the pipe (m/s)
4. Pipe flexibility ratio

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Convert GPa to Pa by multiplying by 10^9.
- Convert mm to m by dividing by 1000.
- Use fluid-only speed a0 = sqrt(K / rho).
- Use pipe flexibility ratio = K x D / (E x e x restraint factor).
- Use restraint factors: fully_restrained = 1.0, anchored_with_expansion = 0.85, unrestrained = 0.7.
- Use flexibility factor = sqrt(1 + pipe flexibility ratio).
- Use wave speed = fluid-only speed / flexibility factor.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "fluid_only_wave_speed_m_s": <numeric_value>,
  "flexibility_factor": <numeric_value>,
  "wave_speed_m_s": <numeric_value>,
  "pipe_flexibility_ratio": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
