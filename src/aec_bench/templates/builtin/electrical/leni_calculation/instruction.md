# ABOUTME: Prompt template for Lighting Energy Numeric Indicator tasks.
# ABOUTME: Presents installed power, hours, factors, area, and reference LENI.

You are a senior interior lighting engineer checking lighting energy performance.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Installed lighting power | {{ installed_lighting_power_w }} | W |
| Annual operating hours | {{ annual_operating_hours }} | h/year |
| Control factor | {{ control_factor }} | - |
| Daylight factor | {{ daylight_factor }} | - |
| Zone area | {{ zone_area_m2 }} | m2 |
| Reference LENI | {{ reference_leni_kwh_m2_year }} | kWh/m2/year |

## Constraints

- Annual lighting energy equals installed power times annual hours times control and daylight factors, divided by 1000.
- LENI equals annual lighting energy divided by zone area.
- Reference saving is the percentage reduction from the reference LENI.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "annual_lighting_energy_kwh": <numeric_value>,
  "leni_kwh_m2_year": <numeric_value>,
  "reference_saving_pct": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
