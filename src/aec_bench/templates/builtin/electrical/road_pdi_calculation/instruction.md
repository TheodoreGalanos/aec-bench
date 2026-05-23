# ABOUTME: Prompt template for road lighting Power Density Index tasks.
# ABOUTME: Presents lighting power, illuminance, and area inputs for calculation.

You are a senior road lighting engineer checking energy efficiency.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Total system power | {{ total_system_power_w }} | W |
| Maintained illuminance | {{ maintained_illuminance_lux }} | lux |
| Illuminated area | {{ illuminated_area_m2 }} | m2 |

## Constraints

- Specific power density equals total system power divided by illuminated area.
- Power Density Index equals total system power divided by maintained illuminance and illuminated area.
- Use the values exactly as given.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "power_density_index_w_per_lux_m2": <numeric_value>,
  "specific_power_density_w_per_m2": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
