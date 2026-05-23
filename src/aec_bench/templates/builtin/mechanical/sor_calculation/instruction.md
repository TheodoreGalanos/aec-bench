You are a senior mechanical engineer specializing in water and wastewater treatment.

## Problem

Calculate surface overflow rate for a clarifier and compare it with an explicit maximum design criterion.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Flow rate | {{ flow_rate_m3_d }} | m3/d |
| Clarifier surface area | {{ clarifier_surface_area_m2 }} | m2 |
| Maximum surface overflow rate | {{ maximum_sor_m3_m2_d }} | m3/m2.d |

{% if archetype_description is defined %}
### Clarifier Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A surface overflow rate calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Surface overflow rate in m3/m2.d
2. Utilisation ratio against the maximum criterion
3. Compliance margin in m3/m2.d
4. Numeric criterion flag, where 1 means satisfied and 0 means not satisfied

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use surface overflow rate = flow rate / clarifier surface area.
- Use utilisation ratio = surface overflow rate / maximum surface overflow rate.
- Use compliance margin = maximum surface overflow rate - surface overflow rate.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "surface_overflow_rate_m3_m2_d": <numeric_value>,
  "utilisation_ratio": <numeric_value>,
  "compliance_margin_m3_m2_d": <numeric_value>,
  "criterion_satisfied": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

