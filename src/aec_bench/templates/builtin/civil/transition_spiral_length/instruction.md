You are a senior civil engineer specializing in railway track geometry and alignment design.

## Problem

Determine the minimum transition spiral length to smoothly introduce curvature and superelevation on a curved track section. Three criteria must be checked and the governing (longest) length adopted.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Maximum speed (V_max) | {{ max_speed_km_h }} | km/h |
| Actual cant (E_a) | {{ actual_cant_mm }} | mm |
| Cant deficiency (C_d) | {{ cant_deficiency_mm }} | mm |
{% if rate_of_change_cant_mm_s is defined %}
| Max rate of change of cant (D_cant) | {{ rate_of_change_cant_mm_s }} | mm/s |
{% endif %}
{% if rate_of_change_cd_mm_s is defined %}
| Max rate of change of cant deficiency (D_cd) | {{ rate_of_change_cd_mm_s }} | mm/s |
{% endif %}
{% if min_twist_ratio is defined %}
| Minimum twist ratio | 1:{{ min_twist_ratio }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A transition spiral calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Minimum spiral length from cant runoff criterion, L_cant (m)
2. Minimum spiral length from rate of change of cant deficiency criterion, L_cd (m)
3. Minimum spiral length from twist rate criterion, L_twist (m)
4. Governing minimum spiral length (m)

## Applicable Standards

- ARTC Engineering Track Standard ETS-05-00 (Track Geometry)
- AREMA Manual for Railway Engineering, Chapter 5 (Track)
- EN 13803 (Railway Applications — Track Alignment Design Parameters)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following formulas:
  - Cant runoff: L_cant = (E_a × V_max) / (3.6 × D_cant)
    - where E_a is actual cant (mm), V_max is speed (km/h), D_cant is max rate of change of cant (mm/s)
  - Cant deficiency rate: L_cd = (C_d × V_max) / (3.6 × D_cd)
    - where C_d is cant deficiency (mm), D_cd is max rate of change of cant deficiency (mm/s)
  - Twist rate: L_twist = E_a × twist_ratio / 1000
    - where twist_ratio is the minimum twist ratio (e.g. 400 means 1 mm cant per 400 mm of track length)
  - The governing spiral length is the maximum of the three values
{% if rate_of_change_cant_mm_s is not defined %}
- Typical rate of change of cant D_cant ranges from 35–55 mm/s depending on corridor type
{% endif %}
{% if rate_of_change_cd_mm_s is not defined %}
- Typical rate of change of cant deficiency D_cd ranges from 25–55 mm/s depending on corridor type
{% endif %}
{% if min_twist_ratio is not defined %}
- Typical minimum twist ratios range from 1:400 to 1:800 depending on corridor type and speed
{% endif %}

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "spiral_length_cant_m": <numeric_value>,
  "spiral_length_cd_m": <numeric_value>,
  "spiral_length_twist_m": <numeric_value>,
  "governing_spiral_length_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
