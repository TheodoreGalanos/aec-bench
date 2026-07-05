You are a staged road and ITS engineer checking a task-owned synthetic SSC-16 package for temporary signals, VMS, CCTV, communications, power, and detour operation during construction.

Use only the task-owned synthetic source pack values shown below for numeric grading. External MUTCD, ITS, NTCIP, work-zone traffic, and temporary services workflows shape the context only; they are not extra data sources for this instance.

## Source Objects

- Product: `SSC-16-LH-04`
- Temporary traffic plan: `TTC-16-PLAN-04`
- Device relocation schedule: `DEVICE-16-RELOC-04`
- Signal timing sheet: `SIGNAL-16-TIMING-04`
- Network topology: `NET-16-TOPO-04`
- Power schedule: `POWER-16-SCHED-04`
- Stage operations memo: `MEMO-16-STAGEOPS-04`

## Source Values

| Item | Value |
|------|-------|
| Crossing width | {{ crossing_width_m }} m |
| Pedestrian walk speed | {{ pedestrian_walk_speed_m_s }} m/s |
| Pedestrian startup time | {{ pedestrian_startup_time_s }} s |
| Provided pedestrian clearance | {{ provided_ped_clearance_s }} s |
| VMS character height | {{ vms_character_height_mm }} mm |
| VMS legibility factor | {{ vms_legibility_factor_m_per_mm }} m/mm |
| Available VMS viewing distance | {{ available_vms_viewing_distance_m }} m |
| Signal controller data | {{ signal_controller_data_mbps }} Mbps |
| VMS data | {{ vms_data_mbps }} Mbps |
| CCTV data | {{ cctv_data_mbps }} Mbps |
| Detector data | {{ detector_data_mbps }} Mbps |
| Gateway overhead | {{ gateway_overhead_mbps }} Mbps |
| Network capacity | {{ network_capacity_mbps }} Mbps |
| CCTV PoE load | {{ cctv_poe_w }} W |
| Detector PoE load | {{ detector_poe_w }} W |
| Router PoE load | {{ router_poe_w }} W |
| VMS modem PoE load | {{ vms_modem_poe_w }} W |
| PoE budget | {{ poe_budget_w }} W |
| Signal controller load | {{ signal_controller_load_w }} W |
| VMS power load | {{ vms_power_load_w }} W |
| Battery backup duration | {{ battery_backup_hours }} h |
| Provided battery energy | {{ provided_battery_kwh }} kWh |
| Allowable detour delay | {{ allowable_detour_delay_s }} s |
| Estimated detour delay | {{ estimated_detour_delay_s }} s |

## Required Checks

- Pedestrian clearance time equals crossing width divided by walk speed plus startup time.
- VMS legibility distance equals character height times the source-owned legibility factor.
- Network and PoE loads are sums of the staged device schedule.
- Battery energy covers signal controller, VMS, and PoE load over the backup duration.
- Detour delay margin is allowable delay minus estimated delay.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack, preserve the source object IDs above, and state whether the baseline checks pass.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pedestrian_clearance_time_s": <numeric_value>,
  "pedestrian_clearance_margin_s": <numeric_value>,
  "required_vms_legibility_distance_m": <numeric_value>,
  "vms_legibility_margin_m": <numeric_value>,
  "network_load_mbps": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "poe_load_w": <numeric_value>,
  "poe_headroom_w": <numeric_value>,
  "battery_required_kwh": <numeric_value>,
  "battery_margin_kwh": <numeric_value>,
  "detour_delay_margin_s": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
