You are an electrical design engineer checking `SSC-05-LH-07`, a task-owned synthetic SSC-05 regional load-flow and voltage-regulation review package.

Use only the task-owned synthetic source pack values below for numeric grading. ETAP, EasyPower, load-flow, voltage-regulation, and PFC workflows shape the context only; this instance does not run those tools or parse a real feeder model, review spreadsheet, or load-flow export.

## Scene

- Design case: `CASE-SSC05-REGIONAL-07`
- SLD and feeder: `SLD-05-FEEDER-07`
- Load scenario: `LOAD-05-SCENARIO-07`
- Feeder/cable schedule: `CABLE-05-FEEDER-07`
- Voltage criterion: `CRIT-05-VOLT-07`
- Review comment: `COMMENT-05-REVIEW-07`
- Response memo: `MEMO-05-RESPONSE-07`

## Source Values

| Item | Value |
|------|-------|
| Base load | {{ base_load_kw }} kW |
| Growth fraction | {{ growth_fraction }} |
| Transformer rating | {{ transformer_kva }} kVA |
| Source power factor | {{ source_power_factor }} |
| Target power factor | {{ target_power_factor }} |
| Feeder voltage | {{ feeder_voltage_kv }} kV |
| Feeder resistance | {{ feeder_r_ohm_per_km }} ohm/km |
| Feeder reactance | {{ feeder_x_ohm_per_km }} ohm/km |
| Feeder length | {{ feeder_length_km }} km |
| Regulator boost | {{ regulator_boost_pu }} pu |
| Minimum voltage | {{ minimum_voltage_pu }} pu |
| Feeder loss | {{ feeder_loss_percent }} % |

Checks:

- Peak load equals base load times one plus the growth fraction.
- Transformer loading equals `peak_load_kw / source_power_factor / transformer_kva x 100`.
- Feeder current equals `peak_load_kw x 1000 / (sqrt(3) x feeder_voltage_kv x 1000 x source_power_factor)`.
- Feeder voltage drop uses the source-owned R, X, power factor, length, and current values.
- Regulated voltage equals `1 - voltage_drop_percent / 100 + regulator_boost_pu`.
- Required PFC equals the peak load times the tangent difference between source and target power-factor angles.
- Overall pass score is `1.0` only when transformer and voltage margins are non-negative and required PFC is positive; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated ETAP/EasyPower evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "peak_load_kw": <numeric_value>,
  "transformer_loading_percent": <numeric_value>,
  "transformer_margin_percent": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "voltage_drop_percent": <numeric_value>,
  "regulated_voltage_pu": <numeric_value>,
  "minimum_voltage_margin_pu": <numeric_value>,
  "required_pfc_kvar": <numeric_value>,
  "feeder_loss_kw": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
