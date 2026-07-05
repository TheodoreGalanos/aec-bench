You are an electrical resilience engineer checking a task-owned synthetic SSC-17 DER resilience and feeder interconnection package.

Use only the task-owned synthetic source pack values shown below for numeric grading. SAM, REopt, and interconnection workflows shape the context only: this instance does not run external software or a real source-pack parser.

## Scene

- Product: `SSC-17-LH-01`
- PV resource/output table: `PV-SSC17-001`
- Load profile: `LOAD-SSC17-001`
- BESS/inverter datasheets: `BESS-SSC17-001`
- SLD and feeder schedule: `SLD-SSC17-001`
- Utility interconnection/export form: `UTIL-SSC17-001`
- Commissioning memo: `MEMO-SSC17-001`

## Source Values

| Item | Value |
| --- | --- |
| PV DC rating | {{ pv_dc_kw }} kW |
| PV AC derate | {{ pv_ac_derate }} |
| Inverter AC rating | {{ inverter_ac_rating_kw }} kW |
| Site minimum load | {{ site_minimum_load_kw }} kW |
| Export limit | {{ export_limit_kw }} kW |
| Critical load | {{ critical_load_kw }} kW |
| Outage duration | {{ outage_duration_hr }} h |
| BESS nominal energy | {{ bess_nominal_kwh }} kWh |
| Maximum depth of discharge | {{ max_depth_of_discharge }} |
| Inverter efficiency | {{ inverter_efficiency }} |
| Generator output | {{ generator_kw }} kW |
| Generator runtime | {{ generator_runtime_hr }} h |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder length | {{ feeder_length_m }} m |
| Feeder current | {{ feeder_current_a }} A |
| Conductor resistance | {{ conductor_resistance_ohm_km }} ohm/km |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |
| Feeder ampacity | {{ feeder_ampacity_a }} A |

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pv_ac_output_kw": <numeric_value>,
  "export_kw": <numeric_value>,
  "export_margin_kw": <numeric_value>,
  "critical_energy_required_kwh": <numeric_value>,
  "usable_bess_energy_kwh": <numeric_value>,
  "generator_energy_kwh": <numeric_value>,
  "resilience_energy_available_kwh": <numeric_value>,
  "autonomy_energy_margin_kwh": <numeric_value>,
  "battery_only_runtime_hr": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "feeder_ampacity_margin_a": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
