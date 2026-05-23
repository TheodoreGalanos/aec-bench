# ABOUTME: Prompt template for road lighting Annual Energy Consumption Index tasks.
# ABOUTME: Presents full-output, dimmed-hour, and area inputs for calculation.

You are a senior road lighting engineer checking annual energy performance.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| System power | {{ system_power_w }} | W |
| Full-output operating hours | {{ full_output_hours_per_year }} | h/year |
| Dimmed operating hours | {{ dimmed_hours_per_year }} | h/year |
| Dimming level | {{ dimming_level_pct }} | % |
| Illuminated area | {{ illuminated_area_m2 }} | m2 |

## Constraints

- Annual energy equals full-output energy plus dimmed energy.
- Dimmed energy uses system power multiplied by the dimming level fraction.
- AECI equals annual energy divided by illuminated area.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "annual_energy_kwh": <numeric_value>,
  "aeci_kwh_per_m2_year": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
