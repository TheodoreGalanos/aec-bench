You are a road ITS and electrical resilience engineer checking a task-owned synthetic SSC-17 field equipment energy package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Road, ITS, CCTV, PV, BESS, and storm exposure workflows shape the context only: this instance does not run external software or a real source-pack parser.

## Scene

- Product: `SSC-17-LH-05`
- Road plan/profile: `ROAD-SSC17-005`
- Field device schedule: `DEVICE-SSC17-005`
- Network topology: `NET-SSC17-005`
- Cabinet load schedule: `CAB-SSC17-005`
- Storm/flood exposure note: `FLOOD-SSC17-005`
- Operations memo: `MEMO-SSC17-005`

## Source Values

| Item | Value |
| --- | --- |
| Luminaire count | {{ luminaire_count }} |
| Luminaire load | {{ luminaire_kw_each }} kW each |
| VMS load | {{ vms_kw }} kW |
| CCTV count | {{ cctv_count }} |
| CCTV load | {{ cctv_kw_each }} kW each |
| Communications load | {{ comms_kw }} kW |
| Outage duration | {{ outage_duration_hr }} h |
| Cabinet battery | {{ cabinet_battery_kwh }} kWh |
| Maximum depth of discharge | {{ max_depth_of_discharge }} |
| Inverter efficiency | {{ inverter_efficiency }} |
| PV rating | {{ pv_kw }} kW |
| Solar hours during event | {{ solar_hours }} h |
| PV performance ratio | {{ pv_performance_ratio }} |
| Cabinet threshold level | {{ cabinet_threshold_level_m }} m |
| Flood HGL | {{ flood_hgl_m }} m |
| Required freeboard | {{ required_freeboard_m }} m |
| PoE budget | {{ poe_budget_w }} W |
| PoE camera load | {{ poe_camera_w_each }} W each |
| PoE switch load | {{ poe_switch_w }} W |
| Required VMS runtime | {{ required_vms_runtime_hr }} h |

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "field_device_load_kw": <numeric_value>,
  "outage_energy_required_kwh": <numeric_value>,
  "usable_battery_energy_kwh": <numeric_value>,
  "pv_energy_available_kwh": <numeric_value>,
  "backup_energy_available_kwh": <numeric_value>,
  "backup_energy_margin_kwh": <numeric_value>,
  "battery_only_runtime_hr": <numeric_value>,
  "vms_runtime_margin_hr": <numeric_value>,
  "cabinet_freeboard_m": <numeric_value>,
  "cabinet_freeboard_margin_m": <numeric_value>,
  "poe_load_w": <numeric_value>,
  "poe_margin_w": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
