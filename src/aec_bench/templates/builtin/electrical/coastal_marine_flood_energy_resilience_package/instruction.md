You are a coastal infrastructure and electrical resilience engineer checking a task-owned synthetic SSC-17 coastal flood energy package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Coastal flood, pump/outfall, equipment elevation, and backup energy workflows shape the context only: this instance does not run external software or a real source-pack parser.

## Scene

- Product: `SSC-17-LH-08`
- Tide/SLR/storm table: `COAST-SSC17-008`
- Site section: `SECTION-SSC17-008`
- Pump/outfall schedule: `PUMP-SSC17-008`
- Electrical equipment layout: `EQUIP-SSC17-008`
- Backup source register: `BACKUP-SSC17-008`
- Flood-resilience memo: `MEMO-SSC17-008`

## Source Values

| Item | Value |
| --- | --- |
| Tide level | {{ tide_level_m }} m |
| SLR allowance | {{ slr_allowance_m }} m |
| Storm surge | {{ storm_surge_m }} m |
| Wave allowance | {{ wave_allowance_m }} m |
| Electrical equipment elevation | {{ electrical_equipment_elevation_m }} m |
| Required equipment freeboard | {{ required_equipment_freeboard_m }} m |
| Outfall obvert level | {{ outfall_obvert_level_m }} m |
| Allowable submergence | {{ allowable_submergence_m }} m |
| Pump flow | {{ pump_flow_m3_s }} m3/s |
| Pump head | {{ pump_head_m }} m |
| Pump efficiency | {{ pump_efficiency }} |
| Pump runtime | {{ pump_runtime_hr }} h |
| Controls load | {{ controls_load_kw }} kW |
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

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "design_flood_level_m": <numeric_value>,
  "equipment_freeboard_m": <numeric_value>,
  "equipment_freeboard_margin_m": <numeric_value>,
  "outfall_submergence_m": <numeric_value>,
  "outfall_submergence_margin_m": <numeric_value>,
  "pump_input_power_kw": <numeric_value>,
  "backup_energy_required_kwh": <numeric_value>,
  "usable_bess_energy_kwh": <numeric_value>,
  "generator_energy_kwh": <numeric_value>,
  "backup_energy_available_kwh": <numeric_value>,
  "backup_energy_margin_kwh": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
