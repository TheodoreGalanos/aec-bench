You are a senior mechanical engineer specializing in wastewater treatment.

## Problem

Calculate secondary clarifier solids loading rate and compare it with an explicit maximum criterion.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Total clarifier flow including return activated sludge | {{ total_flow_m3_d }} | m3/d |
| MLSS concentration | {{ mlss_concentration_mg_l }} | mg/L |
| Clarifier surface area | {{ clarifier_surface_area_m2 }} | m2 |
| Maximum solids loading rate | {{ maximum_slr_kg_m2_h }} | kg/m2.h |

{% if archetype_description is defined %}
### Clarifier Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A solids loading rate calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Solids mass flow in kg/d
2. Solids loading rate in kg/m2.h
3. Utilisation ratio against the maximum criterion
4. Compliance margin in kg/m2.h
5. Numeric criterion flag, where 1 means satisfied and 0 means not satisfied

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use solids mass flow = total flow x MLSS / 1000.
- Use solids loading rate = solids mass flow / clarifier surface area / 24.
- Use utilisation ratio = solids loading rate / maximum solids loading rate.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "solids_mass_flow_kg_d": <numeric_value>,
  "solids_loading_rate_kg_m2_h": <numeric_value>,
  "utilisation_ratio": <numeric_value>,
  "compliance_margin_kg_m2_h": <numeric_value>,
  "criterion_satisfied": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

