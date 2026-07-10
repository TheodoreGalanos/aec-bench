You are a construction dewatering engineer checking a task-owned synthetic SSC-16 package for excavation drawdown, settlement risk, pump duty, temporary generator capacity, battery backup, and feeder voltage drop.

Use only the task-owned synthetic source pack values shown below for numeric grading. External dewatering, settlement, temporary power, and construction inspection workflows shape the context only; they are not extra data sources for this instance.

## Source Objects

- Product: `SSC-16-LH-03`
- Excavation plan: `EXC-16-PLAN-03`
- Groundwater record: `GW-16-REC-03`
- Settlement monitoring table: `SETTLE-16-MON-03`
- Pump schedule: `PUMP-16-SCHED-03`
- Temporary power layout: `POWER-16-LAYOUT-03`
- Dewatering memo: `MEMO-16-DEWATER-03`

## Source Values

| Item | Value |
|------|-------|
| Excavation area | {{ excavation_area_m2 }} m2 |
| Required drawdown | {{ drawdown_m }} m |
| Hydraulic conductivity | {{ hydraulic_conductivity_m_day }} m/day |
| Dewatering influence factor | {{ dewatering_influence_factor }} |
| Pump head | {{ pump_head_m }} m |
| Pump efficiency | {{ pump_efficiency }} |
| Motor efficiency | {{ motor_efficiency }} |
| Selected generator capacity | {{ selected_generator_kw }} kW |
| Compressible layer thickness | {{ compressible_layer_thickness_m }} m |
| Consolidation strain | {{ consolidation_strain }} |
| Allowable settlement | {{ allowable_settlement_mm }} mm |
| Telemetry load | {{ telemetry_load_kw }} kW |
| Backup runtime | {{ backup_runtime_h }} h |
| Provided battery capacity | {{ provided_battery_kwh }} kWh |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder power factor | {{ feeder_power_factor }} |
| Feeder length | {{ feeder_length_km }} km |
| Feeder resistance | {{ feeder_resistance_ohm_km }} ohm/km |
| Allowed voltage drop | {{ allowed_voltage_drop_percent }} percent |

## Required Checks

- Dewatering flow equals excavation area times drawdown times hydraulic conductivity times the source-owned influence factor.
- Hydraulic pump power uses `rho g Q H`; input power divides by pump and motor efficiency.
- Settlement equals layer thickness times consolidation strain.
- Battery energy covers pump input plus telemetry load for the backup runtime.
- Feeder voltage drop uses the source-owned single-phase temporary feeder convention.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack, preserve the source object IDs above, and state whether the baseline checks pass.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "dewatering_flow_l_s": <numeric_value>,
  "pump_hydraulic_power_kw": <numeric_value>,
  "pump_input_power_kw": <numeric_value>,
  "generator_headroom_kw": <numeric_value>,
  "predicted_settlement_mm": <numeric_value>,
  "settlement_margin_mm": <numeric_value>,
  "battery_required_kwh": <numeric_value>,
  "battery_margin_kwh": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
