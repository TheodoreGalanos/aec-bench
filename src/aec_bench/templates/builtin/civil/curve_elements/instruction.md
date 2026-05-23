You are a senior civil engineer specializing in road geometry and horizontal alignment design.

## Problem

Calculate the full set of horizontal curve elements for a simple circular curve.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Curve radius (R) | {{ curve_radius_m }} | m |
| Deflection angle (Δ) | {{ deflection_angle_deg }} | degrees |
{% if ip_chainage_m is defined %}
| IP chainage | {{ ip_chainage_m }} | m |
{% endif %}
{% if pc_chainage_m is defined and ip_chainage_m is not defined %}

### Additional Information

{{ replacement_text }}
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A curve elements calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Tangent length T (m)
2. Arc length L (m)
3. External distance E (m)
4. Mid-ordinate M (m)
5. PC chainage (m) — chainage of the point of curvature
6. PT chainage (m) — chainage of the point of tangency

## Applicable Standards

- Austroads Guide to Road Design Part 3 (AGRD Part 3)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following standard horizontal curve formulas:
  - Tangent length: T = R × tan(Δ/2)
  - Arc length: L = R × Δ (where Δ is in radians)
  - External distance: E = R × (1/cos(Δ/2) − 1)
  - Mid-ordinate: M = R × (1 − cos(Δ/2))
  - PC chainage = IP chainage − T
  - PT chainage = PC chainage + L
{% if ip_chainage_m is not defined %}
  - IP chainage = PC chainage + T (back-calculate from the given PC chainage)
{% endif %}
- Convert the deflection angle from degrees to radians before applying trigonometric functions.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "tangent_length_m": <numeric_value>,
  "arc_length_m": <numeric_value>,
  "external_distance_m": <numeric_value>,
  "mid_ordinate_m": <numeric_value>,
  "pc_chainage_m": <numeric_value>,
  "pt_chainage_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
