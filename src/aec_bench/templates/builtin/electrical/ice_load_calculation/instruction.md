# ABOUTME: Prompt template for iced conductor loading tasks.
# ABOUTME: Presents conductor, ice, wind-on-ice, density, and span inputs.

You are a senior transmission line engineer checking iced conductor loading.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Conductor diameter | {{ conductor_diameter_mm }} | mm |
| Radial ice thickness | {{ ice_thickness_mm }} | mm |
| Ice density | {{ ice_density_kg_m3 }} | kg/m3 |
| Wind-on-ice pressure | {{ wind_on_ice_pressure_pa }} | Pa |
| Span length | {{ span_length_m }} | m |

## Constraints

- Iced conductor diameter equals conductor diameter plus twice the radial ice thickness.
- Ice area is the annular area between the iced and bare conductor diameters.
- Ice weight per metre equals ice area times ice density times 9.81 m/s2.
- Wind-on-ice load per metre equals wind pressure times iced diameter in metres.
- Combined load per metre is the vector result of vertical ice weight and transverse wind-on-ice load.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "iced_conductor_diameter_mm": <numeric_value>,
  "ice_weight_n_per_m": <numeric_value>,
  "total_vertical_load_n_per_m": <numeric_value>,
  "wind_on_ice_load_n_per_m": <numeric_value>,
  "combined_ice_wind_load_n_per_m": <numeric_value>,
  "span_combined_load_n": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
