You are a senior mechanical engineer specializing in room acoustics.

## Problem

Calculate single-band reverberation time using the Sabine formula.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Room volume | {{ room_volume_m3 }} | m3 |
| Floor area | {{ floor_area_m2 }} | m2 |
| Floor absorption coefficient | {{ floor_absorption }} | - |
| Wall area | {{ wall_area_m2 }} | m2 |
| Wall absorption coefficient | {{ wall_absorption }} | - |
| Ceiling area | {{ ceiling_area_m2 }} | m2 |
| Ceiling absorption coefficient | {{ ceiling_absorption }} | - |

{% if archetype_description is defined %}
### Acoustic Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A Sabine RT60 calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Equivalent absorption area (m2)
2. Area-weighted average absorption coefficient
3. Sabine RT60 (s)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use equivalent absorption area A = sum(surface area x absorption coefficient).
- Use average absorption coefficient = A / total surface area.
- Use Sabine reverberation time RT60 = 0.161 x room volume / A.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "equivalent_absorption_area_m2": <numeric_value>,
  "average_absorption_coefficient": <numeric_value>,
  "rt60_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
