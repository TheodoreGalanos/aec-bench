You are a senior civil engineer specializing in road geometry and horizontal alignment design.

## Problem

Determine the required superelevation rate and superelevation development (runoff) length for a horizontal curve.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design speed (V) | {{ design_speed_km_h }} | km/h |
| Curve radius (R) | {{ curve_radius_m }} | m |
{% if side_friction_factor is defined %}
| Side friction factor (f) | {{ side_friction_factor }} | - |
{% endif %}
| Lane width (w) | {{ lane_width_m }} | m |
{% if rotation_rate is defined %}
| Rotation rate | {{ rotation_rate }} | m/m |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A superelevation calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Required superelevation rate e (%)
2. Superelevation development (runoff) length Ls (m)

## Applicable Standards

- Austroads Guide to Road Design Part 3 (AGRD Part 3 §7.5)
- AASHTO A Policy on Geometric Design of Highways and Streets (Green Book)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the point-mass equilibrium equation for superelevation:
  - e + f = V² / (127 × R)
  - Rearranged: e = V² / (127 × R) − f
  - where V is design speed in km/h, R is curve radius in m, f is side friction factor
  - e is a decimal fraction (e.g. 0.04 for 4%); report the result as a percentage
  - If the computed e is negative, clamp to 0 (curve is gentle enough for normal crown)
- Calculate development length using:
  - Ls = (e / 100) × w / rotation_rate
  - where e is superelevation rate (%), w is lane width (m), rotation_rate is the maximum rate of pavement rotation (m/m)
{% if rotation_rate is not defined %}
  - Use a default rotation rate of 0.005 (1:200) if not specified
{% endif %}

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "superelevation_rate_pct": <numeric_value>,
  "development_length_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
