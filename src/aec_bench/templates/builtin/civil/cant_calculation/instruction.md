You are a senior civil engineer specializing in railway track geometry and alignment design.

## Problem

Determine the equilibrium cant (superelevation), cant deficiency, and maximum allowable speed for a curved track section.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design speed (V) | {{ design_speed_km_h }} | km/h |
| Curve radius (R) | {{ curve_radius_m }} | m |
{% if actual_cant_mm is defined %}
| Actual cant (E_a) | {{ actual_cant_mm }} | mm |
{% endif %}
{% if max_cant_deficiency_mm is defined %}
| Max cant deficiency (C_d_max) | {{ max_cant_deficiency_mm }} | mm |
{% endif %}
{% if gauge_type is defined %}
| Gauge type | {{ gauge_type }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A cant calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Equilibrium cant E_eq (mm)
2. Cant deficiency C_d (mm)
3. Maximum allowable speed V_max (km/h)

## Applicable Standards

- ARTC Engineering Track Standard ETS-05-00 (Track Geometry)
- AREMA Manual for Railway Engineering, Chapter 5 (Track)
- FRA 49 CFR Part 213 (Track Safety Standards)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the ARTC/AREMA equilibrium cant formula:
  - E_eq = C * V^2 / R
  - where C = 11.82 for standard gauge (1435 mm), C = 8.90 for narrow gauge (1067 mm)
  - V is design speed in km/h, R is curve radius in metres, E_eq is in mm
- Calculate cant deficiency:
  - C_d = E_eq - E_a
  - where E_a is the actual (applied) cant in mm
- Calculate maximum allowable speed from actual cant and maximum deficiency:
  - V_max = sqrt(R * (E_a + C_d_max) / C)
  - where C_d_max is the maximum allowable cant deficiency in mm
{% if gauge_type is not defined %}
- Use standard gauge (C = 11.82) unless otherwise specified
{% endif %}

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "equilibrium_cant_mm": <numeric_value>,
  "cant_deficiency_mm": <numeric_value>,
  "maximum_speed_km_h": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
