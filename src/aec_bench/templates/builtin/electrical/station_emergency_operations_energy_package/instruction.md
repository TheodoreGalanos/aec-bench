You are an electrical and station operations engineer checking a task-owned synthetic SSC-17 emergency operations energy package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Station egress, emergency power, and load-shed workflows shape the context only: this instance does not run external software or a real source-pack parser.

## Scene

- Product: `SSC-17-LH-06`
- Station plan: `STATION-SSC17-006`
- Population schedule: `POP-SSC17-006`
- Life-safety load schedule: `LIFE-SSC17-006`
- SLD/emergency power basis: `SLD-SSC17-006`
- Load-shed sequence: `SHED-SSC17-006`
- Emergency operations memo: `MEMO-SSC17-006`

## Source Values

| Item | Value |
| --- | --- |
| Emergency lighting | {{ emergency_lighting_kw }} kW |
| Alarm NAC load | {{ alarm_nac_kw }} kW |
| Ventilation load | {{ ventilation_kw }} kW |
| Lift load | {{ lift_kw }} kW |
| Communications load | {{ communications_kw }} kW |
| Outage duration | {{ outage_duration_hr }} h |
| Generator output | {{ generator_kw }} kW |
| Generator runtime | {{ generator_runtime_hr }} h |
| BESS nominal energy | {{ bess_nominal_kwh }} kWh |
| Maximum depth of discharge | {{ max_depth_of_discharge }} |
| Inverter efficiency | {{ inverter_efficiency }} |
| Non-critical load shed | {{ noncritical_load_shed_kw }} kW |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder length | {{ feeder_length_m }} m |
| Feeder current | {{ feeder_current_a }} A |
| Conductor resistance | {{ conductor_resistance_ohm_km }} ohm/km |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "emergency_load_kw": <numeric_value>,
  "required_energy_kwh": <numeric_value>,
  "generator_energy_kwh": <numeric_value>,
  "usable_bess_energy_kwh": <numeric_value>,
  "backup_energy_available_kwh": <numeric_value>,
  "backup_energy_margin_kwh": <numeric_value>,
  "battery_only_runtime_hr": <numeric_value>,
  "generator_capacity_margin_kw": <numeric_value>,
  "load_shed_kw": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
