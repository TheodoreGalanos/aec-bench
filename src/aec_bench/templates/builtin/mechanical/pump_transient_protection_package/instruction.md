You are a mechanical piping engineer checking a task-owned synthetic SSC-11 pump transient, thrust, support, and protection-trip package for one pump-trip case.

Use only the task-owned synthetic source pack values shown below for numeric grading. External Bentley OpenFlows HAMMER, AFT Impulse, Hydraulic Institute, and ASME-style piping-support routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Operating case: `OP-SSC11-TRIP-001`
- P&ID / pipe alignment: `PID-SSC11-401`
- Pump and control scenario: `PUMP-11-DUTY-01`
- Transient event table: `TRANS-11-TRIP-01`
- Support and anchor detail: `SUP-11-ANCH-01`
- Protection setting: `PROT-11-HHP-01`
- Support/protection memo: `MEMO-11-SUPPORT-PROTECT-01`

## Pump, Pipe, And Transient Basis

| Item | Value |
|------|-------|
| Fluid density | {{ fluid_density_kg_m3 }} kg/m3 |
| Fluid bulk modulus | {{ fluid_bulk_modulus_gpa }} GPa |
| Pipe elastic modulus | {{ pipe_elastic_modulus_gpa }} GPa |
| Pipe internal diameter | {{ pipe_internal_diameter_mm }} mm |
| Pipe wall thickness | {{ pipe_wall_thickness_mm }} mm |
| Pipe outer diameter | {{ pipe_outer_diameter_mm }} mm |
| Pipe restraint factor | {{ pipe_restraint_factor }} |
| Flow rate | {{ flow_rate_l_s }} L/s |
| Pump-trip velocity change fraction | {{ velocity_change_fraction }} |
| Suction pressure | {{ suction_pressure_kpa }} kPa |
| Discharge pressure | {{ discharge_pressure_kpa }} kPa |
| Pipe friction loss | {{ pipe_friction_loss_kpa }} kPa |
| Static elevation lift | {{ static_elevation_m }} m |
| Bend angle at SUP-11-ANCH-01 | {{ bend_angle_deg }} degrees |

Transient and pump checks:

- Convert fluid bulk modulus and pipe elastic modulus from GPa to Pa.
- Pipe internal area equals `pi / 4 x internal_diameter^2`, using metres.
- Fluid-only wave speed equals `sqrt(fluid_bulk_modulus_pa / fluid_density_kg_m3)`.
- Pipe flexibility ratio equals `(fluid_bulk_modulus_pa / pipe_elastic_modulus_pa) x (pipe_internal_diameter_mm / pipe_wall_thickness_mm) x pipe_restraint_factor`.
- Wave speed equals `fluid_only_wave_speed / sqrt(1 + pipe_flexibility_ratio)`.
- Flow in m3/s equals `flow_rate_l_s / 1000`.
- Steady velocity equals `flow_m3_s / internal_area_m2`.
- Velocity change equals `steady_velocity x velocity_change_fraction`.
- Joukowsky pressure rise equals `fluid_density x wave_speed x velocity_change / 1000` in kPa.
- Joukowsky pressure head equals pressure rise divided by `fluid_density x 9.81 / 1000`.
- Total dynamic head equals `static_elevation_m + (discharge_pressure_kpa - suction_pressure_kpa + pipe_friction_loss_kpa) / (fluid_density x 9.81 / 1000)`.
- Hydraulic power equals `fluid_density x 9.81 x flow_m3_s x total_dynamic_head_m / 1000`.
- Peak transient pressure equals discharge pressure plus Joukowsky pressure rise.
- Bend transient thrust equals `2 x peak_transient_pressure_kpa x internal_area_m2 x sin(bend_angle_deg / 2)`.

## Support And Protection Basis

| Item | Value |
|------|-------|
| Steel density | {{ steel_density_kg_m3 }} kg/m3 |
| Insulation thickness | {{ insulation_thickness_mm }} mm |
| Insulation density | {{ insulation_density_kg_m3 }} kg/m3 |
| Support span | {{ support_span_m }} m |
| Valve weight | {{ valve_weight_kn }} kN |
| Actuator weight | {{ actuator_weight_kn }} kN |
| PROT-11-HHP-01 high-high trip setpoint | {{ high_high_trip_setpoint_kpa }} kPa |
| Pipe MAWP | {{ pipe_mawp_kpa }} kPa |
| Allowable bend thrust | {{ thrust_allowable_kn }} kN |
| Allowable support vertical service load | {{ support_vertical_allowable_kn }} kN |

Support and protection checks:

- Steel annulus area equals `pi / 4 x (outer_diameter^2 - internal_diameter^2)`, using metres.
- Insulation outer diameter equals pipe outer diameter plus twice the insulation thickness.
- Insulation annulus area equals `pi / 4 x (insulation_outer_diameter^2 - pipe_outer_diameter^2)`, using metres.
- Each line load equals `area x density x 9.81 / 1000` in kN/m.
- Operating line load equals steel line load plus fluid contents line load plus insulation line load.
- Support vertical service load equals `operating_line_load x support_span + valve_weight + actuator_weight`.
- Pressure trip margin equals high-high trip setpoint minus peak transient pressure.
- Pipe pressure margin equals pipe MAWP minus peak transient pressure.
- Thrust utilization equals bend transient thrust divided by allowable bend thrust.
- Support vertical utilization equals support vertical service load divided by allowable support vertical service load.
- Overall pass score is `1.0` only when pressure trip margin, pipe pressure margin, thrust margin, and support vertical margin are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "fluid_only_wave_speed_m_s": <numeric_value>,
  "pipe_flexibility_ratio": <numeric_value>,
  "wave_speed_m_s": <numeric_value>,
  "steady_velocity_m_s": <numeric_value>,
  "velocity_change_m_s": <numeric_value>,
  "joukowsky_pressure_rise_kpa": <numeric_value>,
  "joukowsky_pressure_head_m": <numeric_value>,
  "total_dynamic_head_m": <numeric_value>,
  "hydraulic_power_kw": <numeric_value>,
  "peak_transient_pressure_kpa": <numeric_value>,
  "bend_transient_thrust_kn": <numeric_value>,
  "operating_line_load_kn_m": <numeric_value>,
  "support_vertical_service_kn": <numeric_value>,
  "pressure_trip_margin_kpa": <numeric_value>,
  "pipe_pressure_margin_kpa": <numeric_value>,
  "thrust_utilization": <numeric_value>,
  "support_vertical_utilization": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
