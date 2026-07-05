You are a mechanical process piping engineer checking a task-owned synthetic SSC-11 valve, line, control, and thrust package.

Use only the task-owned synthetic source pack values shown below for numeric grading. ISA-style control loop checks, valve Cv sizing workflows, P&ID line-list coordination, and pipe thrust routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-11-LH-03`
- P&ID excerpt: `PID-SSC11-003`
- Line list: `LINE-SSC11-003`
- Valve datasheet: `VALVE-SSC11-003`
- Control loop card: `LOOP-SSC11-003`
- Coordination memo: `MEMO-SSC11-003`

## Source Values

| Item | Value |
|------|-------|
| Process flow | {{ process_flow_m3_h }} m3/h |
| Liquid specific gravity | {{ liquid_specific_gravity }} |
| Valve pressure drop | {{ valve_pressure_drop_kpa }} kPa |
| Installed valve Cv | {{ installed_valve_cv }} |
| Pipe internal diameter | {{ pipe_internal_diameter_mm }} mm |
| Maximum velocity | {{ maximum_velocity_m_s }} m/s |
| Maximum pressure loss | {{ maximum_pressure_loss_kpa }} kPa |
| Bend line pressure | {{ line_pressure_kpa }} kPa |
| Signal low value | {{ signal_low_value }} |
| Signal high value | {{ signal_high_value }} |
| Process value | {{ process_value }} |
| Signal low | {{ signal_low_ma }} mA |
| Signal high | {{ signal_high_ma }} mA |
| Bend angle | {{ bend_angle_deg }} degrees |
| Bend thrust allowable | {{ thrust_allowable_kn }} kN |

## Checks

- Required valve Cv equals `flow_gpm x sqrt(specific_gravity / pressure_drop_psi)`.
- Pipe velocity equals flow divided by pipe area.
- Pressure-loss margin equals maximum pressure loss minus valve pressure drop.
- Control signal uses linear scaling between the low and high process values and the 4-20 mA range.
- Bend thrust equals `2 x pressure x pipe_area x sin(bend_angle / 2)`.
- Overall pass score is `1.0` only when valve Cv, velocity, pressure-loss, and thrust margins pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "required_valve_cv": <numeric_value>,
  "valve_cv_margin": <numeric_value>,
  "pipe_velocity_m_s": <numeric_value>,
  "velocity_margin_m_s": <numeric_value>,
  "pressure_loss_margin_kpa": <numeric_value>,
  "control_signal_ma": <numeric_value>,
  "bend_thrust_kn": <numeric_value>,
  "thrust_utilization": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
