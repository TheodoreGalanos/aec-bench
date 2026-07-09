You are an electrical/coastal resilience engineer checking a task-owned synthetic SSC-04 coastal pump-out and generator autonomy package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External pump-station, flood-event, emergency-power, fuel-autonomy, BESS, and operational-continuity workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-04-LH-07`
- Pump station section: `PUMPSTA-04-SECTION-07`
- Flood event table: `FLOOD-04-EVENT-07`
- Pump duty sheet: `PUMP-04-DUTY-07`
- Electrical load schedule: `LOAD-04-ELEC-07`
- Backup fuel and BESS sheet: `BACKUP-04-FUEL-07`
- Continuity memo: `MEMO-04-CONTINUITY-07`

## Source Values

| Item | Value |
|------|-------|
| Inflow rate | {{ inflow_rate_m3_s }} m3/s |
| Event duration | {{ event_duration_h }} h |
| Pump discharge | {{ pump_discharge_m3_s }} m3/s |
| Available storage | {{ available_storage_m3 }} m3 |
| Flood level | {{ flood_level_m }} m |
| Sump low level | {{ sump_low_level_m }} m |
| Piping losses | {{ piping_losses_m }} m |
| Pump efficiency | {{ pump_efficiency }} |
| Motor efficiency | {{ motor_efficiency }} |
| Active pump count | {{ active_pump_count }} |
| Controls load | {{ controls_load_kw }} kW |
| Lighting load | {{ lighting_load_kw }} kW |
| Generator capacity | {{ generator_capacity_kw }} kW |
| Generator derate factor | {{ generator_derate_factor }} |
| Fuel volume | {{ fuel_volume_l }} L |
| Fuel consumption | {{ fuel_consumption_l_h }} L/h |
| Required runtime | {{ required_runtime_h }} h |
| BESS capacity | {{ bess_capacity_kwh }} kWh |
| BESS usable fraction | {{ bess_usable_fraction }} |
| Minimum BESS runtime | {{ minimum_bess_runtime_h }} h |
| Access elevation | {{ access_elevation_m }} m |
| Required access freeboard | {{ required_access_freeboard_m }} m |

## Checks

- Inflow volume equals inflow rate times event duration times 3600.
- Pumped volume equals pump discharge times event duration times 3600.
- Storage margin equals available storage plus pumped volume minus inflow volume.
- Pump total dynamic head equals flood level minus sump low level plus piping losses.
- Pump input power equals `1000 x 9.81 x pump discharge x total dynamic head / 1000 / (pump efficiency x motor efficiency)`.
- Emergency load equals pump input power times active pump count plus controls and lighting loads.
- Generator capacity margin equals derated generator capacity minus emergency load.
- Fuel runtime margin equals fuel volume divided by consumption rate minus required runtime.
- BESS runtime equals usable BESS energy divided by emergency load.
- Access freeboard margin equals access elevation minus flood level and required access freeboard.
- Overall pass score is `1.0` only when storage, generator, fuel, BESS runtime, and access checks pass; otherwise it is `0.0`.

## Output Format

Write a compact continuity memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "inflow_volume_m3": <numeric_value>,
  "pumped_volume_m3": <numeric_value>,
  "storage_margin_m3": <numeric_value>,
  "pump_total_dynamic_head_m": <numeric_value>,
  "pump_input_power_kw": <numeric_value>,
  "emergency_load_kw": <numeric_value>,
  "generator_capacity_margin_kw": <numeric_value>,
  "fuel_runtime_margin_h": <numeric_value>,
  "bess_runtime_h": <numeric_value>,
  "access_freeboard_margin_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
