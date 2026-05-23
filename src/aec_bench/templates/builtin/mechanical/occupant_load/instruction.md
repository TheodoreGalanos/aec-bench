You are a senior fire and life-safety engineer specializing in prescriptive occupancy checks.

## Problem

Calculate occupant load from floor area and an explicit area-per-occupant criterion.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Floor area | {{ floor_area_m2 }} | m2 |
| Area per occupant | {{ area_per_occupant_m2 }} | m2/person |

{% if archetype_description is defined %}
### Occupancy Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An occupant load calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Calculated occupant load before rounding
2. Design occupant load rounded up to a whole person
3. Occupant density in persons per m2

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use only the explicit area-per-occupant criterion provided.
- Round design occupants up to the next whole person.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "calculated_occupants": <numeric_value>,
  "design_occupants": <numeric_value>,
  "occupant_density_person_m2": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

