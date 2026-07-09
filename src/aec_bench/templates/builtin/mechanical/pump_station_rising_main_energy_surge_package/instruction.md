You are a mechanical pump-station engineer checking a task-owned synthetic SSC-11 rising-main energy, surge, and feeder package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Hazen-Williams hydraulic calculations, Joukowsky surge screening, pump duty energy checks, and feeder voltage-drop coordination routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-11-LH-06`
- Pump duty note: `PUMP-SSC11-006`
- Rising-main profile: `PROFILE-SSC11-006`
- Pipe pressure basis: `PIPE-SSC11-006`
- Feeder schedule: `FEED-SSC11-006`
- Coordination memo: `MEMO-SSC11-006`

## Source Values

| Item | Value |
|------|-------|
| Flow | {{ flow_l_s }} L/s |
| Static head | {{ static_head_m }} m |
| Rising-main length | {{ rising_main_length_m }} m |
| Pipe internal diameter | {{ pipe_internal_diameter_mm }} mm |
| Hazen-Williams C | {{ hazen_williams_c }} |
| Pump efficiency | {{ pump_efficiency }} |
| Motor efficiency | {{ motor_efficiency }} |
| Surge velocity-change fraction | {{ velocity_change_fraction }} |
| Wave speed | {{ wave_speed_m_s }} m/s |
| Fluid density | {{ fluid_density_kg_m3 }} kg/m3 |
| Base pressure | {{ base_pressure_kpa }} kPa |
| Pipe pressure class | {{ pipe_pressure_class_kpa }} kPa |
| High-high trip setpoint | {{ high_high_trip_setpoint_kpa }} kPa |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Motor power factor | {{ motor_power_factor }} |
| Feeder length | {{ feeder_length_km }} km |
| Conductor resistance | {{ conductor_resistance_ohm_km }} ohm/km |
| Allowable voltage drop | {{ allowable_voltage_drop_percent }} percent |

## Checks

- Hazen-Williams loss equals `10.67 x length x flow^1.852 / (C^1.852 x diameter^4.871)`, using m3/s and m.
- Total dynamic head equals static head plus friction head.
- Hydraulic power equals `density x 9.81 x flow x TDH / 1000`.
- Motor input power divides hydraulic power by pump and motor efficiencies.
- Surge pressure rise equals `density x wave_speed x velocity_change / 1000`.
- Peak pressure equals base pressure plus surge pressure rise.
- Feeder current uses three-phase power, voltage, and power factor.
- Overall pass score is `1.0` only when pressure trip, pipe pressure, and voltage-drop margins pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "hazen_williams_loss_m": <numeric_value>,
  "total_dynamic_head_m": <numeric_value>,
  "hydraulic_power_kw": <numeric_value>,
  "motor_input_power_kw": <numeric_value>,
  "steady_velocity_m_s": <numeric_value>,
  "surge_pressure_rise_kpa": <numeric_value>,
  "peak_transient_pressure_kpa": <numeric_value>,
  "pressure_trip_margin_kpa": <numeric_value>,
  "pipe_pressure_margin_kpa": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
