# ABOUTME: Prompt template for conductor wind load tasks.
# ABOUTME: Presents pressure, terrain, height, conductor diameter, drag, and span.

You are a senior transmission line engineer checking conductor wind load.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Wind pressure at 10 m | {{ wind_pressure_pa }} | Pa |
| Conductor diameter | {{ conductor_diameter_mm }} | mm |
| Span length | {{ span_length_m }} | m |
| Drag coefficient | {{ drag_coefficient }} | - |
| Terrain category | {{ terrain_category }} | - |
| Height above ground | {{ height_above_ground_m }} | m |

## Constraints

- Use terrain exponent 0.16 for `open`, 0.22 for `suburban`, and 0.30 for `urban`.
- Height-adjusted wind pressure equals wind pressure times `(height / 10)^terrain_exponent`.
- Wind load per unit length equals adjusted pressure times conductor diameter in metres times drag coefficient.
- Transverse wind load equals wind load per unit length times span length.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "height_adjusted_wind_pressure_pa": <numeric_value>,
  "wind_load_per_unit_length_n_m": <numeric_value>,
  "transverse_wind_load_n": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
