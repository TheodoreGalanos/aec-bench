You are a mechanical engineer checking a task-owned synthetic SSC-06 compressor and pneumatic system package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Compressed-air demand, receiver storage, motor, and feeder workflows shape the context only; this instance does not run external software or parse a real source pack.

## Scene

- Product: `SSC-06-LH-03`
- Air demand table: `AIR-06-DEMAND-03`
- Compressor data sheet: `COMP-06-DATA-03`
- Receiver/storage schedule: `RECEIVER-06-STORAGE-03`
- Motor schedule: `MOTOR-06-SCHED-03`
- Feeder schedule: `FEEDER-06-480V-03`
- Compressed-air memo: `MEMO-06-AIR-03`

## Source Values

| Item | Value |
| --- | --- |
| Connected air demand | {{ connected_air_demand_m3_min }} m3/min |
| Simultaneity factor | {{ simultaneity_factor }} |
| Leakage allowance | {{ leakage_allowance_fraction }} |
| Selected compressor capacity | {{ selected_compressor_capacity_m3_min }} m3/min |
| Receiver volume | {{ receiver_volume_m3 }} m3 |
| Receiver pressure band | {{ receiver_pressure_band_kpa }} kPa |
| Atmospheric pressure | {{ atmospheric_pressure_kpa_abs }} kPa abs |
| Compressor specific power | {{ compressor_specific_power_kw_per_m3_min }} kW per m3/min |
| Motor efficiency | {{ motor_efficiency }} |
| Selected motor size | {{ selected_motor_kw }} kW |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder length | {{ feeder_length_km }} km |
| Feeder resistance | {{ feeder_resistance_ohm_per_km }} ohm/km |
| Feeder reactance | {{ feeder_reactance_ohm_per_km }} ohm/km |
| Motor power factor | {{ motor_power_factor }} |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |
| Branch pressure loss | {{ branch_pressure_loss_kpa }} kPa |
| Maximum branch pressure loss | {{ max_branch_pressure_loss_kpa }} kPa |

## Calculation Rules

- Adjusted air demand equals `connected_air_demand_m3_min x simultaneity_factor x (1 + leakage_allowance_fraction)`.
- Compressor capacity margin equals selected compressor capacity minus adjusted demand.
- Receiver storage runtime equals `receiver_volume_m3 x receiver_pressure_band_kpa / atmospheric_pressure_kpa_abs / adjusted_air_demand_m3_min`.
- Compressor shaft power equals adjusted demand times compressor specific power.
- Motor input power equals compressor shaft power divided by motor efficiency.
- Motor size margin equals selected motor size minus motor input power.
- Feeder current uses three-phase apparent power from motor input and power factor.
- Feeder voltage drop percent uses conductor resistance, reactance, feeder length, motor power factor, and reactive factor.
- Pressure drop margin equals maximum branch pressure loss minus branch pressure loss.
- Overall pass score is `1.0` only when capacity, motor, voltage-drop, and pressure-loss margins are non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "adjusted_air_demand_m3_min": <numeric_value>,
  "compressor_capacity_margin_m3_min": <numeric_value>,
  "receiver_storage_runtime_min": <numeric_value>,
  "compressor_shaft_power_kw": <numeric_value>,
  "motor_input_power_kw": <numeric_value>,
  "motor_size_margin_kw": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "pressure_drop_margin_kpa": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
