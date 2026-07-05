You are a mechanical piping reviewer checking a task-owned synthetic SSC-11 piping network repair and negative-case portfolio.

Use only the task-owned synthetic source pack values shown below for numeric grading. Piping network hydraulic review, repair option comparison workflows, pipe thrust support checks, and negative-case verification portfolios shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-11-LH-08`
- Baseline network case: `BASE-SSC11-008`
- Repair variant case: `VAR-SSC11-008`
- Support movement note: `SUP-SSC11-008`
- Negative-case register: `VERIFY-SSC11-008`
- Coordination memo: `MEMO-SSC11-008`

## Source Values

| Item | Value |
|------|-------|
| Baseline flow | {{ baseline_flow_l_s }} L/s |
| Variant flow | {{ variant_flow_l_s }} L/s |
| Pipe internal diameter | {{ pipe_internal_diameter_mm }} mm |
| Pipe length | {{ pipe_length_m }} m |
| Darcy friction factor | {{ darcy_friction_factor }} |
| Baseline valve loss coefficient | {{ baseline_valve_loss_coefficient }} |
| Variant valve loss coefficient | {{ variant_valve_loss_coefficient }} |
| Measured support shift | {{ measured_support_shift_m }} m |
| Allowed support shift | {{ allowed_support_shift_m }} m |
| Bend pressure | {{ bend_pressure_kpa }} kPa |
| Bend angle | {{ bend_angle_deg }} degrees |
| Thrust allowable | {{ thrust_allowable_kn }} kN |
| Expected negative cases | {{ expected_negative_cases }} |
| Localized negative cases | {{ localized_negative_cases }} |
| Unresolved repair count | {{ unresolved_repair_count }} |
| Maximum variant velocity | {{ maximum_variant_velocity_m_s }} m/s |

## Checks

- Baseline and variant velocity each equal flow divided by pipe area.
- Baseline and variant headloss each include Darcy major loss and valve minor loss.
- Velocity delta equals variant velocity minus baseline velocity.
- Headloss delta equals variant headloss minus baseline headloss.
- Bend thrust equals `2 x pressure x pipe_area x sin(bend_angle / 2)`.
- Negative-case capture percent equals localized negative cases divided by expected cases times 100.
- Overall pass score is `1.0` only when variant velocity, thrust utilization, support shift, negative-case capture, and unresolved repair checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "baseline_velocity_m_s": <numeric_value>,
  "variant_velocity_m_s": <numeric_value>,
  "velocity_delta_m_s": <numeric_value>,
  "baseline_headloss_m": <numeric_value>,
  "variant_headloss_m": <numeric_value>,
  "headloss_delta_m": <numeric_value>,
  "bend_thrust_kn": <numeric_value>,
  "thrust_utilization": <numeric_value>,
  "support_shift_margin_m": <numeric_value>,
  "negative_case_capture_percent": <numeric_value>,
  "unresolved_repair_count": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
