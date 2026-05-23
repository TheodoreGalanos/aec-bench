You are a senior civil engineer specializing in stormwater management and drainage design.

## Problem

Estimate the required detention basin volume to attenuate post-development peak flow to the allowable release rate, using a simplified triangular hydrograph method.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Post-development peak flow (Q_post) | {{ post_dev_peak_flow_m3_s }} | m³/s |
{% if allowable_release_rate_m3_s is defined %}
| Allowable release rate (Q_allow) | {{ allowable_release_rate_m3_s }} | m³/s |
{% endif %}
| Design storm duration (t_storm) | {{ storm_duration_hr }} | hr |
| Design water depth | {{ design_depth_m }} | m |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A detention volume calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Required detention storage volume (m³)
2. Approximate basin surface area at design depth (m²)

## Applicable Standards

- TR-55 — Urban Hydrology for Small Watersheds
- Local council stormwater detention requirements

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the simplified triangular hydrograph method:
  - **Triangular inflow hydrograph:** peak = Q_post, base = t_storm
    - Inflow volume = Q_post × t_storm × 3600 / 2
  - **Constant outflow** at Q_allow during the storm
    - Outflow volume = Q_allow × t_storm × 3600
  - **Required storage volume** depends on the relationship between Q_allow and Q_post:
    - If Q_allow < Q_post/2:
      V = t_storm × 3600 × (Q_post/2 − Q_allow)
    - If Q_allow ≥ Q_post/2:
      V = (Q_post − Q_allow)² × t_storm × 3600 / (2 × Q_post)
    - If Q_allow ≥ Q_post, no detention is needed (V = 0)
  - **Approximate surface area:** A_surface = V / design_depth
- If Q_allow is not given directly, infer a reasonable value from the site description and local detention requirements

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "required_storage_volume_m3": <numeric_value>,
  "approximate_surface_area_m2": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
