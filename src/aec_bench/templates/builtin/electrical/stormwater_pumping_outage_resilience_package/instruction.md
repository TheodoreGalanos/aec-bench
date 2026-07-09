You are an electrical and stormwater resilience engineer checking a task-owned synthetic SSC-17 stormwater pumping outage package for one storm event and utility outage.

Use only the task-owned synthetic source pack values shown below for numeric grading. EPA SWMM and NREL REopt style workflows shape the context only: this instance does not run SWMM, REopt, or a real source-pack parser.

## Scene

- Resilience case: `CASE-SSC17-PUMP-OUTAGE-001`
- Operating scenario: `SCEN-17-STORM-OUTAGE-01`
- Outage ledger: `TIME-17-OUTAGE-LEDGER-01`
- Rainfall/inflow trace: `RAIN-17-HYETO-01`
- Stormwater pump: `PUMP-17-STORM-01`
- Wet-well/storage basin: `BASIN-17-WETWELL-01`
- Critical load schedule: `LOAD-17-CRITICAL-01`
- Battery energy storage: `BESS-17-BACKUP-01`
- Backup generator: `GEN-17-BACKUP-01`
- Pump feeder: `FEEDER-17-480V-01`
- Controls and telemetry node: `CTRL-17-RTU-01`
- Resilience memo: `MEMO-17-RESILIENCE-01`

## Stormwater And Pumping Basis

| Item | Value |
|------|-------|
| Storm inflow | {{ storm_inflow_m3_s }} m3/s |
| Outage duration | {{ outage_duration_hr }} h |
| Pump capacity | {{ pump_capacity_m3_s }} m3/s |
| Allowed pump runtime during outage | {{ allowed_pump_runtime_hr }} h |
| Available wet-well/storage volume | {{ available_storage_volume_m3 }} m3 |
| Pump total head | {{ pump_total_head_m }} m |
| Pump efficiency | {{ pump_efficiency }} |

Stormwater and pump checks:

- Storm inflow volume equals `storm_inflow_m3_s x outage_duration_hr x 3600`.
- Pumpable volume equals `pump_capacity_m3_s x allowed_pump_runtime_hr x 3600`.
- Residual storage volume equals `max(storm_inflow_volume_m3 - pumpable_volume_m3, 0)`.
- Storage margin equals available storage volume minus residual storage volume.
- Pump hydraulic power equals `1000 x 9.81 x pump_capacity_m3_s x pump_total_head_m / 1000` in kW.
- Pump input power equals pump hydraulic power divided by pump efficiency.

## Backup Energy And Feeder Basis

| Item | Value |
|------|-------|
| Controls load | {{ controls_load_kw }} kW |
| Telemetry load | {{ telemetry_load_kw }} kW |
| BESS nominal energy | {{ bess_nominal_kwh }} kWh |
| Maximum BESS depth of discharge | {{ max_depth_of_discharge }} |
| Inverter efficiency | {{ inverter_efficiency }} |
| Generator output | {{ generator_kw }} kW |
| Generator runtime | {{ generator_runtime_hr }} h |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder length | {{ feeder_length_m }} m |
| Feeder current | {{ feeder_current_a }} A |
| Conductor resistance | {{ conductor_resistance_ohm_km }} ohm/km |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |

Backup energy and feeder checks:

- Critical mixed load equals pump input power plus controls load plus telemetry load.
- Pump energy required equals pump input power times allowed pump runtime.
- Controls energy required equals `(controls_load_kw + telemetry_load_kw) x outage_duration_hr`.
- Total energy required equals pump energy required plus controls energy required.
- Usable BESS energy equals `bess_nominal_kwh x max_depth_of_discharge x inverter_efficiency`.
- Generator energy equals `generator_kw x generator_runtime_hr`.
- Backup energy available equals usable BESS energy plus generator energy.
- Backup energy margin equals backup energy available minus total energy required.
- Battery-only mixed-load runtime equals usable BESS energy divided by critical mixed load.
- Feeder voltage drop percent uses the source-owned three-phase approximation `sqrt(3) x feeder_current_a x feeder_length_m x conductor_resistance_ohm_km / 1000 / feeder_voltage_v x 100`.
- Voltage drop margin equals maximum voltage drop percent minus feeder voltage drop percent.
- Overall pass score is `1.0` only when storage margin, backup energy margin, and voltage drop margin are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated SWMM or REopt evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "storm_inflow_volume_m3": <numeric_value>,
  "pumpable_volume_m3": <numeric_value>,
  "residual_storage_volume_m3": <numeric_value>,
  "storage_margin_m3": <numeric_value>,
  "pump_hydraulic_power_kw": <numeric_value>,
  "pump_input_power_kw": <numeric_value>,
  "critical_mixed_load_kw": <numeric_value>,
  "pump_energy_required_kwh": <numeric_value>,
  "controls_energy_required_kwh": <numeric_value>,
  "total_energy_required_kwh": <numeric_value>,
  "usable_bess_energy_kwh": <numeric_value>,
  "generator_energy_kwh": <numeric_value>,
  "backup_energy_available_kwh": <numeric_value>,
  "backup_energy_margin_kwh": <numeric_value>,
  "battery_only_mixed_load_runtime_hr": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
