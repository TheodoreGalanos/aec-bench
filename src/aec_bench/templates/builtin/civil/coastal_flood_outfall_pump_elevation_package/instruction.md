You are a civil/coastal engineer checking a task-owned synthetic SSC-04 coastal flood, outfall, pump, and electrical elevation package for one coastal pump station and flap-gated outfall.

Use only the task-owned synthetic source pack values shown below for numeric grading. External NOAA sea-level-rise scenarios, FEMA flood utility guidance, FHWA HEC-22 drainage/outfall practice, and USACE Coastal Engineering Manual routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Coastal case ledger: `CASE-SSC04-COASTAL-001`
- Datum note: `DATUM-04-AHD-01`
- Tide, SLR, and storm horizon table: `TIDE-04-HORIZON-01`
- Flap-gated outfall schedule: `OUTFALL-04-FLAP-01`
- Flood pump schedule: `PUMP-04-FLOOD-01`
- Wet-well/basin storage note: `BASIN-04-WETWELL-01`
- Electrical switchboard and controls layout: `ELEC-04-SWBD-01`
- Pump feeder schedule: `FEEDER-04-PUMP-01`
- Flood resilience memo: `MEMO-04-RESILIENCE-01`

All elevations are in the same source datum from `DATUM-04-AHD-01`. Do not mix datums or substitute a different tide table.

Unit convention for this source pack:

- Water levels and elevations are in metres on the source datum.
- Flow in `m3/s` times seconds gives event volume in `m3`.
- Pump hydraulic power in kW is `1000 x 9.81 x pump_discharge_m3_s x head_m / 1000`.
- Electrical feeder voltage drop uses kW converted to W for the current calculation.

## Coastal Level And Outfall Basis

| Item | Value |
|------|-------|
| Present mean sea level | {{ present_mean_sea_level_m }} m |
| Tidal amplitude | {{ tidal_amplitude_m }} m |
| Sea-level-rise allowance | {{ sea_level_rise_allowance_m }} m |
| Storm-surge allowance | {{ storm_surge_allowance_m }} m |
| Wave/runup allowance | {{ wave_runup_allowance_m }} m |
| Equipment freeboard allowance | {{ equipment_freeboard_allowance_m }} m |
| Outfall invert level | {{ outfall_invert_level_m }} m |

Outfall and level checks:

- Model the tide as `water_level = mean_sea_level + tidal_amplitude x sin(theta)`.
- The fraction of a tide cycle above the outfall invert equals `0.5 - asin((outfall_invert_level_m - mean_sea_level_m) / tidal_amplitude_m) / pi` when the ratio is between -1 and 1.
- Present submergence uses `present_mean_sea_level_m`.
- Future submergence uses `present_mean_sea_level_m + sea_level_rise_allowance_m`.
- Submergence increase equals future submergence percent minus present submergence percent.
- Design stillwater level equals `present_mean_sea_level_m + tidal_amplitude_m + sea_level_rise_allowance_m + storm_surge_allowance_m`.
- Design flood level equals `design_stillwater_level_m + wave_runup_allowance_m`.
- Minimum equipment elevation equals `design_flood_level_m + equipment_freeboard_allowance_m`.

## Pump And Storage Basis

| Item | Value |
|------|-------|
| Peak inflow during tide-locked event | {{ peak_inflow_m3_s }} m3/s |
| Tide-locked duration | {{ tide_locked_duration_h }} h |
| Pump discharge | {{ pump_discharge_m3_s }} m3/s |
| Available wet-well/basin storage | {{ available_storage_m3 }} m3 |
| Wet-well low operating level | {{ wetwell_low_operating_level_m }} m |
| Pipe, valve, and flap-gate losses | {{ pipe_and_valve_losses_m }} m |
| Pump efficiency | {{ pump_efficiency }} |
| Motor efficiency | {{ motor_efficiency }} |
| Selected motor power | {{ selected_motor_power_kw }} kW |

Pump and storage checks:

- Event seconds equal `tide_locked_duration_h x 3600`.
- Inflow volume equals `peak_inflow_m3_s x event_seconds`.
- Pumped volume equals `pump_discharge_m3_s x event_seconds`.
- Storage margin equals `available_storage_m3 + pumped_volume_m3 - inflow_volume_m3`.
- Pump total dynamic head equals `design_flood_level_m - wetwell_low_operating_level_m + pipe_and_valve_losses_m`.
- Pump hydraulic power equals `1000 x 9.81 x pump_discharge_m3_s x pump_total_dynamic_head_m / 1000`.
- Pump motor input power equals `pump_hydraulic_power_kw / (pump_efficiency x motor_efficiency)`.
- Pump motor margin equals `selected_motor_power_kw - pump_motor_input_kw`.

## Electrical Elevation And Feeder Basis

| Item | Value |
|------|-------|
| Switchboard elevation | {{ switchboard_elevation_m }} m |
| Pump controls elevation | {{ controls_elevation_m }} m |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Motor power factor | {{ motor_power_factor }} |
| Feeder resistance | {{ feeder_resistance_ohm_km }} ohm/km |
| Feeder reactance | {{ feeder_reactance_ohm_km }} ohm/km |
| Feeder length | {{ feeder_length_km }} km |
| Voltage-drop limit | {{ voltage_drop_limit_percent }} percent |

Electrical checks:

- Switchboard freeboard margin equals `switchboard_elevation_m - minimum_equipment_elevation_m`.
- Controls freeboard margin equals `controls_elevation_m - minimum_equipment_elevation_m`.
- Feeder current equals `pump_motor_input_kw x 1000 / (sqrt(3) x feeder_voltage_v x motor_power_factor)`.
- Let `sin_phi = sqrt(1 - motor_power_factor^2)`.
- Feeder voltage drop percent equals `sqrt(3) x feeder_current_a x (feeder_resistance_ohm_km x motor_power_factor + feeder_reactance_ohm_km x sin_phi) x feeder_length_km / feeder_voltage_v x 100`.
- Voltage-drop margin equals `voltage_drop_limit_percent - feeder_voltage_drop_percent`.
- Overall pass score is `1.0` only when storage margin, pump motor margin, switchboard freeboard margin, controls freeboard margin, and voltage-drop margin are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact flood resilience memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "present_submergence_percent": <numeric_value>,
  "future_submergence_percent": <numeric_value>,
  "submergence_increase_percent": <numeric_value>,
  "design_stillwater_level_m": <numeric_value>,
  "design_flood_level_m": <numeric_value>,
  "minimum_equipment_elevation_m": <numeric_value>,
  "inflow_volume_m3": <numeric_value>,
  "pumped_volume_m3": <numeric_value>,
  "storage_margin_m3": <numeric_value>,
  "pump_total_dynamic_head_m": <numeric_value>,
  "pump_hydraulic_power_kw": <numeric_value>,
  "pump_motor_input_kw": <numeric_value>,
  "pump_motor_margin_kw": <numeric_value>,
  "switchboard_freeboard_margin_m": <numeric_value>,
  "controls_freeboard_margin_m": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
