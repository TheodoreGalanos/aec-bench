You are a senior civil/structural engineer specializing in wind loading for buildings and structures.

## Problem

Calculate the design site wind speed for a building using AS/NZS 1170.2 Section 2.2.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Regional wind speed (V_R) | {{ regional_wind_speed_m_per_s }} | m/s |
{% if terrain_category is defined %}
| Terrain category | {{ terrain_category }} | - |
{% endif %}
| Building height (z) | {{ building_height_m }} | m |
| Topographic multiplier (M_t) | {{ topographic_multiplier }} | - |
{% if shielding_multiplier is defined %}
| Shielding multiplier (M_s) | {{ shielding_multiplier }} | - |
{% endif %}
{% if wind_direction_multiplier is defined %}
| Wind direction multiplier (M_d) | {{ wind_direction_multiplier }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A wind speed calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Terrain/height multiplier M_z,cat from Table 4.1(A)
2. Site wind speed V_sit,beta (m/s)

## Applicable Standards

- AS/NZS 1170.2:2021 — Structural design actions, Part 2: Wind actions

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the site wind speed equation from Section 2.2:
  - V_sit,beta = V_R x M_d x M_z,cat x M_s x M_t
- Determine M_z,cat from Table 4.1(A) based on the terrain category and building height:
  - For heights between tabulated values, use linear interpolation
  - For heights below 3 m, use the 3 m row values
  - Terrain categories are: 1 (open water/flat), 2 (open grassland), 2.5 (lightly built), 3 (suburban), 4 (dense urban)
{% if wind_direction_multiplier is not defined %}
- If no wind direction multiplier is specified, assume M_d = 1.0 (non-directional analysis)
{% endif %}

## Output Format

Show your step-by-step working in Markdown, including table lookups and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "mz_cat": <numeric_value>,
  "site_wind_speed_m_per_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
