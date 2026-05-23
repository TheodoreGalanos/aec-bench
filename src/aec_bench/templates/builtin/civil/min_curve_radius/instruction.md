You are a senior civil engineer specializing in road geometry and horizontal alignment design.

## Problem

Determine the minimum horizontal curve radius and the desirable minimum horizontal curve radius for a road alignment.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design speed (V) | {{ design_speed_km_h }} | km/h |
| Maximum superelevation rate (e_max) | {{ max_superelevation_pct }} | % |
{% if side_friction_factor is defined %}
| Side friction factor (f) | {{ side_friction_factor }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A minimum curve radius calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Absolute minimum horizontal curve radius R_min (m)
2. Desirable minimum horizontal curve radius R_desirable (m)

## Applicable Standards

- Austroads Guide to Road Design Part 3 (AGRD Part 3 §7)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the point-mass equilibrium equation for minimum curve radius:
  - R_min = V² / (127 × (e_max + f))
  - where V is design speed in km/h, e_max is the maximum superelevation rate as a decimal (e.g. 0.06 for 6%), and f is the side friction factor
- For the desirable minimum radius, use a reduced friction factor of 0.7 × f:
  - R_desirable = V² / (127 × (e_max + 0.7 × f))
{% if side_friction_factor is not defined %}
- Side friction factors from AGRD Table 7.5 (speed → f):
  40 km/h → 0.35, 50 → 0.33, 60 → 0.30, 70 → 0.26, 80 → 0.22, 90 → 0.19, 100 → 0.16, 110 → 0.13, 120 → 0.11, 130 → 0.09
{% endif %}

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "min_radius_m": <numeric_value>,
  "desirable_min_radius_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
