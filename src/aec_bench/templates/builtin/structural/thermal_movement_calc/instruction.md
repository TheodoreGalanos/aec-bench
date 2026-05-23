You are a senior structural engineer specializing in facade movement and tolerance checks.

## Problem

Calculate thermal expansion and contraction for a structural or facade component, then determine the movement accommodation required.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Member length L | {{ member_length_mm }} | mm |
| Design temperature range delta T | {{ temperature_range_c }} | C |
{% if coefficient_thermal_expansion_microstrain_c is defined %}
| Coefficient of thermal expansion alpha | {{ coefficient_thermal_expansion_microstrain_c }} | microstrain/C |
{% endif %}
| Joint safety factor | {{ joint_safety_factor }} | - |

{% if archetype_description is defined %}
### Component Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A thermal movement calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Total thermal movement over the design temperature range (mm)
2. Expansion movement from the neutral temperature (mm)
3. Contraction movement from the neutral temperature (mm)
4. Movement accommodation required after applying the allowance factor (mm)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Convert alpha from microstrain/C to strain/C by multiplying by 10^-6.
- Use delta L = alpha x L x delta T.
- Treat expansion and contraction as symmetric about the neutral installation temperature.
- Use accommodation required = total thermal movement x joint safety factor.
- If alpha is not given, infer an appropriate value from the material description.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "thermal_movement_mm": <numeric_value>,
  "expansion_movement_mm": <numeric_value>,
  "contraction_movement_mm": <numeric_value>,
  "accommodation_required_mm": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
