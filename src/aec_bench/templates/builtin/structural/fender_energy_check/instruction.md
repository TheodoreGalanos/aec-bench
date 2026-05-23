You are a senior structural engineer specializing in marine fender systems.

## Problem

Calculate corrected fender energy absorption capacity and compare it with the design berthing energy.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design berthing energy ED | {{ design_berthing_energy_knm }} | kNm |
| Fender rated energy ER | {{ fender_rated_energy_knm }} | kNm |
| Temperature factor | {{ temperature_factor }} | - |
| Velocity factor | {{ velocity_factor }} | - |
| Angular factor | {{ angular_factor }} | - |
| Manufacturing tolerance factor | {{ manufacturing_tolerance_factor }} | - |

{% if archetype_description is defined %}
### Fender Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A fender energy calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Total correction factor
2. Corrected fender energy capacity (kNm)
3. Energy utilisation ratio
4. Capacity margin (kNm)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use correction factor = temperature factor x velocity factor x angular factor x manufacturing tolerance factor.
- Use corrected capacity = rated fender energy x correction factor.
- Use energy utilisation ratio = design berthing energy / corrected capacity.
- Use capacity margin = corrected capacity - design berthing energy.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "correction_factor": <numeric_value>,
  "corrected_capacity_knm": <numeric_value>,
  "energy_utilisation_ratio": <numeric_value>,
  "capacity_margin_knm": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
