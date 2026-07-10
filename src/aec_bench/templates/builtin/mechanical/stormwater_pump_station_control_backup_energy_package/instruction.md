You are a mechanical stormwater pump-station engineer checking a task-owned synthetic SSC-03 pump control and backup-energy package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Hazen-Williams hydraulic calculations, stormwater pump station controls, pump duty power workflows, and backup energy sizing shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-03-LH-03`
- Wet-well and pump schedule: `WETWELL-SSC03-003`
- Inflow event table: `INFLOW-SSC03-003`
- Rising-main profile: `RMAIN-SSC03-003`
- Controls load schedule: `CTRL-SSC03-003`
- Backup energy schedule: `ENERGY-SSC03-003`
- Flood-control memo: `MEMO-SSC03-003`

## Source Values

| Item | Value |
|------|-------|
| Pump capacity | {{ pump_capacity_l_s }} L/s |
| Pump count | {{ pump_count }} |
| Peak inflow | {{ inflow_peak_l_s }} L/s |
| Static head | {{ static_head_m }} m |
| Rising-main length | {{ rising_main_length_m }} m |
| Pipe internal diameter | {{ pipe_internal_diameter_mm }} mm |
| Hazen-Williams C | {{ hazen_williams_c }} |
| Pump efficiency | {{ pump_efficiency }} |
| Motor efficiency | {{ motor_efficiency }} |
| Fluid density | {{ fluid_density_kg_m3 }} kg/m3 |
| Control panel load | {{ control_panel_load_kw }} kW |
| Telemetry load | {{ telemetry_load_kw }} kW |
| Outage duration | {{ outage_duration_hr }} h |
| Usable battery energy | {{ usable_battery_energy_kwh }} kWh |
| Wet-well high water level | {{ wetwell_high_water_level_m }} m |
| Access level | {{ access_level_m }} m |
| Minimum wet-well freeboard | {{ minimum_wetwell_freeboard_m }} m |

## Checks

- Total pump capacity equals pump capacity times pump count.
- Hazen-Williams loss uses flow in m3/s and diameter in m.
- Hydraulic power equals `density x 9.81 x flow x total_dynamic_head / 1000`.
- Backup energy required equals control load times outage duration.
- Overall pass score is `1.0` only when pump capacity, backup energy, and wet-well freeboard checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated SWMM report-output evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "total_pump_capacity_l_s": <numeric_value>,
  "pump_capacity_margin_l_s": <numeric_value>,
  "hazen_williams_loss_m": <numeric_value>,
  "total_dynamic_head_m": <numeric_value>,
  "rising_main_velocity_m_s": <numeric_value>,
  "hydraulic_power_kw": <numeric_value>,
  "motor_input_power_kw": <numeric_value>,
  "control_load_kw": <numeric_value>,
  "backup_energy_required_kwh": <numeric_value>,
  "backup_energy_margin_kwh": <numeric_value>,
  "wetwell_freeboard_m": <numeric_value>,
  "wetwell_freeboard_margin_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
