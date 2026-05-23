You are a senior coastal engineer estimating tidal exchange through an inlet.

## Problem

Calculate the tidal prism, inlet flow area, mean tidal flow rate, and mean inlet velocity for the basin.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Basin surface area | {{ basin_surface_area_m2 }} | m2 |
| Tidal range | {{ tidal_range_m }} | m |
| Inlet width | {{ inlet_width_m }} | m |
| Inlet average depth | {{ inlet_average_depth_m }} | m |
{% if exchange_duration_h is defined %}
| Exchange duration | {{ exchange_duration_h }} | h |
{% endif %}
{% if archetype_description is defined %}

### Site Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A tidal prism calculation tool is available at `/workspace/tidal-prism_calc.py`. Run it with:

```bash
python3 /workspace/tidal-prism_calc.py --help
```
{% endif %}

## Required

Calculate:

1. Tidal prism volume in m3
2. Inlet flow area in m2
3. Mean tidal flow rate in m3/s
4. Mean inlet velocity in m/s

## Constraints

- Use `tidal_prism = basin_surface_area x tidal_range`.
- Use `inlet_flow_area = inlet_width x inlet_average_depth`.
- Use `mean_tidal_flow = tidal_prism / exchange_duration_seconds`.
- Use `mean_tidal_velocity = mean_tidal_flow / inlet_flow_area`.

## Output Format

Show your working in Markdown. At the end, include a JSON block with exactly these keys:

```json
{
  "tidal_prism_m3": <numeric_value>,
  "inlet_flow_area_m2": <numeric_value>,
  "mean_tidal_flow_m3_s": <numeric_value>,
  "mean_tidal_velocity_m_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
