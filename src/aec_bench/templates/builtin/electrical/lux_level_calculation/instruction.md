# ABOUTME: Prompt template for room lumen-method illuminance tasks.
# ABOUTME: Presents room, luminaire, utilisation, maintenance, and target inputs.

You are a senior building lighting engineer checking a reduced lumen-method calculation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Room length | {{ room_length_m }} | m |
| Room width | {{ room_width_m }} | m |
| Luminaire count | {{ luminaire_count }} | count |
| Luminaire luminous flux | {{ luminaire_luminous_flux_lm }} | lm |
| Utilisation factor | {{ utilisation_factor }} | - |
| Maintenance factor | {{ maintenance_factor }} | - |
| Total lighting power | {{ total_lighting_power_w }} | W |
| Minimum illuminance | {{ minimum_illuminance_lux }} | lux |
| Target illuminance | {{ target_illuminance_lux }} | lux |

## Constraints

- Room area equals length times width.
- Average illuminance equals total lamp lumens times utilisation factor times maintenance factor divided by room area.
- Uniformity ratio equals minimum illuminance divided by average illuminance.
- Specific luminaire power density equals total power divided by room area and divided by average illuminance per 100 lux.
- Target margin is the percentage difference between average and target illuminance.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "average_illuminance_lux": <numeric_value>,
  "uniformity_ratio_uo": <numeric_value>,
  "specific_luminaire_power_density_w_m2_100lux": <numeric_value>,
  "target_illuminance_margin_pct": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
