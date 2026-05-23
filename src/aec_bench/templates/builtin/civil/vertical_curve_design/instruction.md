You are a senior civil engineer specializing in railway track geometry and vertical alignment design.

## Problem

Determine the algebraic grade difference, minimum vertical curve radius, and minimum vertical curve length for a railway grade transition.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Initial grade (g1) | {{ initial_grade_pct }} | % |
| Final grade (g2) | {{ final_grade_pct }} | % |
| Design speed (V) | {{ design_speed_km_h }} | km/h |
{% if max_vertical_acceleration_m_s2 is defined %}
| Max vertical acceleration (a_v) | {{ max_vertical_acceleration_m_s2 }} | m/s² |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A vertical curve design tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Algebraic grade difference A (%)
2. Minimum vertical curve radius R_v (m)
3. Minimum vertical curve length L_v (m)

## Applicable Standards

- ARTC Engineering Track Standard ETS-05-00 (Track Geometry)
- AREMA Manual for Railway Engineering, Chapter 5 (Track)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following formulae for vertical curve design:
  - Algebraic grade difference: A = |g1 - g2| where g1 and g2 are grades in percent (positive = uphill)
  - Minimum vertical curve radius: R_v = V² / (3.6² × a_v) where V is design speed in km/h and a_v is acceptable vertical acceleration in m/s²
  - Minimum vertical curve length: L_v = (A / 100) × R_v where A is in percent and R_v is in metres
{% if max_vertical_acceleration_m_s2 is not defined %}
- The acceptable vertical acceleration depends on the type of rail service and passenger comfort requirements
{% endif %}

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "algebraic_grade_difference_pct": <numeric_value>,
  "min_vertical_curve_radius_m": <numeric_value>,
  "min_vertical_curve_length_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
