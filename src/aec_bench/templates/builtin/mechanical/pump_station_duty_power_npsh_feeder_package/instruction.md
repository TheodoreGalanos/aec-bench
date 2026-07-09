You are a pump station design engineer checking a task-owned synthetic SSC-06 pump station duty, power, NPSH, and feeder package.

Use only the task-owned synthetic source pack values shown below for numeric grading. EPA EPANET, Datacor Fathom, PIPE-FLO, PUMP-FLO, vendor pump-selection, and Hydraulic Institute style workflows shape the context only; this instance does not run those tools or parse a real vendor curve export.

## Scene

- Pump duty case: `CASE-SSC06-PUMP-DUTY-001`
- Equipment tag: `EQUIP-06-PUMP-01`
- Wet-well schedule: `WW-06-WETWELL-01`
- Rising main: `RM-06-RISING-MAIN-01`
- Pump curve table: `CURVE-06-PUMP-01`
- Motor schedule: `MOTOR-06-SCHED-01`
- NPSH basis: `NPSH-06-SUCTION-01`
- Feeder schedule: `FEEDER-06-480V-01`
- Selection memo: `MEMO-06-SELECTION-01`

## Hydraulic Duty Basis

| Item | Value |
|------|-------|
| Design flow | {{ design_flow_l_s }} L/s |
| Static lift | {{ static_lift_m }} m |
| Rising-main length | {{ rising_main_length_m }} m |
| Rising-main diameter | {{ rising_main_diameter_mm }} mm |
| Hazen-Williams C | {{ hazen_williams_c }} |
| Minor-loss coefficient | {{ minor_loss_coefficient }} |
| CURVE-06-PUMP-01 head at duty | {{ pump_curve_head_at_duty_m }} m |

Hydraulic checks:

- Convert design flow to m3/s as `design_flow_l_s / 1000`.
- Convert pipe diameter to m as `rising_main_diameter_mm / 1000`.
- Hazen-Williams headloss equals `10.67 x length_m x flow_m3_s^1.852 / (C^1.852 x diameter_m^4.87)`.
- Flow velocity equals `flow_m3_s / (pi x diameter_m^2 / 4)`.
- Minor loss equals `minor_loss_coefficient x velocity^2 / (2 x 9.81)`.
- Total dynamic head equals static lift plus Hazen-Williams headloss plus minor loss.
- Pump curve head margin equals `pump_curve_head_at_duty_m - total_dynamic_head_m`.

## Motor, NPSH, And Feeder Basis

| Item | Value |
|------|-------|
| Fluid density | {{ fluid_density_kg_m3 }} kg/m3 |
| Pump efficiency | {{ pump_efficiency_pct }} % |
| Motor efficiency | {{ motor_efficiency_pct }} % |
| Motor service factor | {{ motor_service_factor }} |
| Selected motor size | {{ selected_motor_kw }} kW |
| Atmospheric pressure | {{ atmospheric_pressure_kpa_abs }} kPa abs |
| Vapor pressure | {{ vapor_pressure_kpa_abs }} kPa abs |
| Wet-well minimum level above pump | {{ wetwell_min_level_above_pump_m }} m |
| Suction loss | {{ suction_loss_m }} m |
| NPSH required | {{ npsh_required_m }} m |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder length | {{ feeder_length_km }} km |
| Feeder resistance | {{ feeder_resistance_ohm_per_km }} ohm/km |
| Feeder reactance | {{ feeder_reactance_ohm_per_km }} ohm/km |
| Motor power factor | {{ motor_power_factor }} |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |

Motor, NPSH, and feeder checks:

- Hydraulic power equals `fluid_density_kg_m3 x 9.81 x flow_m3_s x total_dynamic_head_m / 1000`.
- Shaft power equals hydraulic power divided by pump efficiency as a decimal.
- Motor input power equals shaft power divided by motor efficiency as a decimal.
- Required motor power equals shaft power times motor service factor.
- Motor size margin equals selected motor size minus required motor power.
- NPSH available equals `(atmospheric_pressure_kpa_abs - vapor_pressure_kpa_abs) x 1000 / (fluid_density_kg_m3 x 9.81) + wetwell_min_level_above_pump_m - suction_loss_m`.
- NPSH margin equals NPSH available minus NPSH required.
- NPSH margin ratio equals NPSH available divided by NPSH required.
- Load reactive power equals `motor_input_power_kw x tan(acos(motor_power_factor))`.
- Apparent power equals `sqrt(motor_input_power_kw^2 + load_reactive_power_kvar^2)`.
- Feeder current equals `apparent_power_kva x 1000 / (sqrt(3) x feeder_voltage_v)`.
- Feeder voltage drop percent equals `sqrt(3) x feeder_current_a x feeder_length_km x (feeder_resistance_ohm_per_km x motor_power_factor + feeder_reactance_ohm_per_km x reactive_factor) / feeder_voltage_v x 100`, where `reactive_factor = load_reactive_power_kvar / apparent_power_kva`.
- Voltage drop margin equals maximum voltage drop percent minus feeder voltage drop percent.
- Overall pass score is `1.0` only when pump curve head margin, NPSH margin, motor size margin, and voltage drop margin are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated EPANET/Fathom/PIPE-FLO/PUMP-FLO evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "hazen_williams_headloss_m": <numeric_value>,
  "flow_velocity_m_s": <numeric_value>,
  "minor_loss_m": <numeric_value>,
  "total_dynamic_head_m": <numeric_value>,
  "pump_curve_head_margin_m": <numeric_value>,
  "hydraulic_power_kw": <numeric_value>,
  "shaft_power_kw": <numeric_value>,
  "motor_input_power_kw": <numeric_value>,
  "required_motor_power_kw": <numeric_value>,
  "motor_size_margin_kw": <numeric_value>,
  "npsh_available_m": <numeric_value>,
  "npsh_margin_m": <numeric_value>,
  "npsh_margin_ratio": <numeric_value>,
  "load_reactive_power_kvar": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
