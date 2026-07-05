You are an electrical and fire-safety interface engineer checking a task-owned synthetic BESS fire, containment, ventilation, and feeder package.

Use only the task-owned synthetic source pack values shown below for numeric grading. BESS safety, containment, ventilation, and feeder workflows shape the context only: this instance does not run external software or a real source-pack parser.

## Scene

- SSC-17 Product: `SSC-17-LH-04`
- SSC-17 BESS/inverter datasheets: `BESS-SSC17-004`
- SSC-17 SLD/cable schedule: `SLD-SSC17-004`
- SSC-17 battery-room/container layout: `ROOM-SSC17-004`
- SSC-17 fire strategy: `FIRE-SSC17-004`
- SSC-17 ventilation and containment schedule: `VENT-SSC17-004`
- SSC-17 safety memo: `MEMO-SSC17-004`
- SSC-19 Product: `SSC-19-LH-02`
- SSC-19 BESS data sheet: `BESS-19-DATA-02`
- SSC-19 fire strategy: `FIRE-19-STRAT-02`
- SSC-19 ventilation schedule: `VENT-19-SCHED-02`
- SSC-19 containment detail: `CONTAIN-19-DETAIL-02`
- SSC-19 BESS SLD: `SLD-19-BESS-02`
- SSC-19 safety memo: `MEMO-19-SAFETY-02`

## Source Values

| Item | Value |
| --- | --- |
| BESS nominal energy | {{ bess_nominal_kwh }} kWh |
| Maximum depth of discharge | {{ max_depth_of_discharge }} |
| Inverter efficiency | {{ inverter_efficiency }} |
| Room volume | {{ room_volume_m3 }} m3 |
| Required air changes | {{ required_air_changes_h }} ACH |
| Fan power density | {{ fan_power_density_kw_m3_s }} kW/(m3/s) |
| Emergency duration | {{ emergency_duration_hr }} h |
| Battery module count | {{ battery_module_count }} |
| Module HRR | {{ module_hrr_kw }} kW |
| Propagation factor | {{ propagation_factor }} |
| Containment rating | {{ containment_rating_kw }} kW |
| Alarm load | {{ alarm_load_kw }} kW |
| Suppression load | {{ suppression_load_kw }} kW |
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
  "usable_bess_energy_kwh": <numeric_value>,
  "ventilation_airflow_m3_s": <numeric_value>,
  "ventilation_fan_power_kw": <numeric_value>,
  "ventilation_energy_kwh": <numeric_value>,
  "design_hrr_kw": <numeric_value>,
  "containment_hrr_margin_kw": <numeric_value>,
  "safety_load_kw": <numeric_value>,
  "safety_energy_required_kwh": <numeric_value>,
  "safety_energy_margin_kwh": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
