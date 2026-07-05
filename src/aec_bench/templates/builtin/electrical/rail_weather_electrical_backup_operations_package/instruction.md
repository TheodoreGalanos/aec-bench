You are a rail electrical resilience engineer checking a task-owned synthetic SSC-17 rail weather and backup operations package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Rail weather, OLE/feeder, signalling, and degraded operations workflows shape the context only: this instance does not run external software or a real source-pack parser.

## Scene

- Product: `SSC-17-LH-07`
- Route profile/span schedule: `RAIL-SSC17-007`
- Weather table: `WEATHER-SSC17-007`
- Signalling load schedule: `SIGNAL-SSC17-007`
- Feeder/OLE basis: `FEEDER-SSC17-007`
- Operations rule: `RULE-SSC17-007`
- Rail resilience memo: `MEMO-SSC17-007`

## Source Values

| Item | Value |
| --- | --- |
| Signal load | {{ signal_load_kw }} kW |
| Communications load | {{ communications_load_kw }} kW |
| Weather heating load | {{ weather_heating_kw }} kW |
| Outage duration | {{ outage_duration_hr }} h |
| Weather heating duration | {{ weather_heating_duration_hr }} h |
| Battery nominal energy | {{ battery_nominal_kwh }} kWh |
| Maximum depth of discharge | {{ max_depth_of_discharge }} |
| Inverter efficiency | {{ inverter_efficiency }} |
| Generator output | {{ generator_kw }} kW |
| Generator runtime | {{ generator_runtime_hr }} h |
| Derated thermal rating | {{ derated_thermal_rating_a }} A |
| Operating current | {{ operating_current_a }} A |
| Allowable sag | {{ allowable_sag_m }} m |
| Calculated sag | {{ calculated_sag_m }} m |
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
  "signal_comms_load_kw": <numeric_value>,
  "weather_heating_energy_kwh": <numeric_value>,
  "required_backup_energy_kwh": <numeric_value>,
  "usable_battery_energy_kwh": <numeric_value>,
  "generator_energy_kwh": <numeric_value>,
  "backup_energy_available_kwh": <numeric_value>,
  "backup_energy_margin_kwh": <numeric_value>,
  "battery_only_runtime_hr": <numeric_value>,
  "thermal_rating_margin_a": <numeric_value>,
  "sag_margin_m": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
