# ABOUTME: Prompt template for basic BESS sizing tasks.
# ABOUTME: Presents discharge duty, SOC window, efficiency, and EOL retention.

You are a senior power systems engineer sizing a battery energy storage system.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Required discharge power | {{ required_discharge_power_mw }} | MW |
| Required discharge duration | {{ required_discharge_duration_h }} | h |
| Usable SOC range | {{ usable_soc_range_pct }} | % |
| Round-trip efficiency | {{ round_trip_efficiency_pct }} | % |
| End-of-life capacity retention | {{ end_of_life_capacity_retention_pct }} | % |

## Constraints

- Usable energy equals required discharge power times discharge duration.
- Nominal energy capacity equals usable energy divided by usable SOC fraction and round-trip efficiency fraction.
- Beginning-of-life capacity equals nominal energy capacity divided by end-of-life retention fraction.
- Nominal power rating equals the required discharge power.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "nominal_power_rating_mw": <numeric_value>,
  "usable_energy_mwh": <numeric_value>,
  "nominal_energy_capacity_mwh": <numeric_value>,
  "beginning_of_life_capacity_mwh": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
