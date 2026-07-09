You are an electrical product reviewer checking a task-owned synthetic SSC-15 cable/component datasheet package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Product directories, listing systems, and standards workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-15-LH-02`
- Cable datasheet: `DAT-15-CABLE-02`
- Cable schedule: `SCHED-15-CABLE-02`
- Temperature/installation table: `TEMP-15-INSTALL-02`
- Single-line diagram feeder: `SLD-15-FEEDER-02`
- Manufacturer limits: `LIMIT-15-MFR-02`
- Component compliance memo: `MEMO-15-CABLE-02`

All checks use the same product identity and feeder. Do not change the cable code, feeder, installation case, or manufacturer limit unless you explicitly flag a source conflict.

## Source Values

| Item | Value |
|------|-------|
| Design current | {{ design_current_a }} A |
| Datasheet ampacity | {{ datasheet_ampacity_a }} A |
| Ambient derating factor | {{ ambient_derating_factor }} |
| Grouping derating factor | {{ grouping_derating_factor }} |
| Installation derating factor | {{ installation_derating_factor }} |
| Base resistance | {{ base_resistance_ohm_km }} ohm/km |
| Temperature coefficient | {{ temperature_coefficient }} |
| Operating temperature | {{ operating_temperature_c }} degC |
| Reference temperature | {{ reference_temperature_c }} degC |
| Skin-effect factor | {{ skin_effect_factor }} |
| Reactance | {{ reactance_ohm_km }} ohm/km |
| Power factor | {{ power_factor }} |
| Circuit length | {{ circuit_length_m }} m |
| Voltage | {{ voltage_v }} V |
| Maximum voltage drop | {{ max_voltage_drop_percent }} percent |
| Temperature rating | {{ temperature_rating_c }} degC |
| Matching identity fields | {{ matching_identity_fields }} |
| Required identity fields | {{ required_identity_fields }} |

Derated ampacity equals datasheet ampacity times all derating factors. AC resistance equals base resistance times the temperature correction and skin-effect factor.

## Output Format

Write a compact component compliance memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "derated_ampacity_a": <numeric_value>,
  "ampacity_margin_a": <numeric_value>,
  "ampacity_utilization": <numeric_value>,
  "ac_resistance_ohm_km": <numeric_value>,
  "voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "temperature_rating_margin_c": <numeric_value>,
  "product_identity_match_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
