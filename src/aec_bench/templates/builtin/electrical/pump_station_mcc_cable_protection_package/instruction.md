You are an electrical design engineer checking `SSC-05-LH-05`, a task-owned synthetic SSC-05 pump station MCC, cable, and protection package.

Use only the task-owned synthetic source pack values below for numeric grading. MCC, cable-ampacity, voltage-drop, motor-starting, and protection workflows shape the context only; this instance does not run those tools or parse a real pump schedule, MCC SLD, cable schedule, or protection table.

## Scene

- Design case: `CASE-SSC05-PUMP-MCC-05`
- Pump schedule: `PUMP-05-SCHED-05`
- MCC single line: `MCC-05-SLD-05`
- Cable schedule: `CABLE-05-PUMP-05`
- Protection setting table: `PROT-05-SET-05`
- Pump duty/load basis: `DUTY-05-BASIS-05`
- Power design memo: `MEMO-05-POWER-05`

## Source Values

| Item | Value |
|------|-------|
| Pump motor power | {{ pump_motor_kw }} kW |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Motor efficiency | {{ motor_efficiency }} |
| Motor power factor | {{ motor_power_factor }} |
| Starting multiplier | {{ starting_multiplier }} |
| Base cable ampacity | {{ base_cable_ampacity_a }} A |
| Ambient derating factor | {{ ambient_derating_factor }} |
| Grouping derating factor | {{ grouping_derating_factor }} |
| Installation derating factor | {{ installation_derating_factor }} |
| Voltage-drop factor | {{ voltage_drop_mv_per_a_m }} mV/A/m |
| Feeder length | {{ feeder_length_m }} m |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |
| Overload setting | {{ overload_setting_a }} A |
| Available fault current | {{ available_fault_current_ka }} kA |
| Breaker interrupt rating | {{ breaker_interrupt_rating_ka }} kA |

Checks:

- Running current equals `pump_motor_kw x 1000 / (sqrt(3) x feeder_voltage_v x motor_efficiency x motor_power_factor)`.
- Starting current equals running current times the starting multiplier.
- Derated cable ampacity equals the base ampacity times all three derating factors.
- Voltage drop percent equals `voltage_drop_mv_per_a_m x running_current_a x feeder_length_m / 1000 / feeder_voltage_v x 100`.
- Overall pass score is `1.0` only when ampacity, voltage-drop, overload, and fault margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated SKM evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "running_current_a": <numeric_value>,
  "starting_current_a": <numeric_value>,
  "derated_cable_ampacity_a": <numeric_value>,
  "ampacity_margin_a": <numeric_value>,
  "voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overload_setting_margin_a": <numeric_value>,
  "short_circuit_margin_ka": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
