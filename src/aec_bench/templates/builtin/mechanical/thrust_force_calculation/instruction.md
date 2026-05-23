You are a senior mechanical engineer specializing in pipe thrust restraint.

## Problem

Calculate the unbalanced thrust force at a pressurised pipe bend.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Internal pressure | {{ internal_pressure_kpa }} | kPa |
| Pipe internal diameter | {{ pipe_internal_diameter_mm }} | mm |
| Bend angle | {{ bend_angle_deg }} | degrees |

{% if archetype_description is defined %}
### Pipe Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A thrust force calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Pipe internal area
2. Straight pressure force
3. Bend thrust force

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use pipe area = pi x diameter squared / 4.
- Use pressure force = pressure x pipe area.
- Use bend thrust = 2 x pressure force x sin(bend angle / 2).

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "pipe_area_m2": <numeric_value>,
  "pressure_force_kn": <numeric_value>,
  "bend_thrust_force_kn": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

