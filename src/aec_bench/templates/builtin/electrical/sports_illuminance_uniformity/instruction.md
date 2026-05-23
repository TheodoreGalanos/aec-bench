# ABOUTME: Prompt template for sports field illuminance uniformity tasks.
# ABOUTME: Presents field, luminaire, utilisation, maintenance, and grid values.

You are a senior sports lighting engineer checking horizontal illuminance and uniformity.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Field length | {{ field_length_m }} | m |
| Field width | {{ field_width_m }} | m |
| Luminaire count | {{ luminaire_count }} | count |
| Luminaire luminous flux | {{ luminaire_luminous_flux_lm }} | lm |
| Utilisation factor | {{ utilisation_factor }} | - |
| Maintenance factor | {{ maintenance_factor }} | - |
| Minimum illuminance | {{ minimum_illuminance_lux }} | lux |
| Maximum illuminance | {{ maximum_illuminance_lux }} | lux |
| Target average illuminance | {{ target_average_illuminance_lux }} | lux |
| Target U2 uniformity | {{ target_uniformity_u2 }} | - |

## Constraints

- Field area equals length times width.
- Average horizontal illuminance equals total luminaire lumens times utilisation factor times maintenance factor divided by field area.
- U1 equals minimum illuminance divided by maximum illuminance.
- U2 equals minimum illuminance divided by average horizontal illuminance.
- Margins are percentage differences from the target average illuminance and target U2.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "average_horizontal_illuminance_lux": <numeric_value>,
  "uniformity_u1_min_max": <numeric_value>,
  "uniformity_u2_min_avg": <numeric_value>,
  "average_illuminance_margin_pct": <numeric_value>,
  "uniformity_u2_margin_pct": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
