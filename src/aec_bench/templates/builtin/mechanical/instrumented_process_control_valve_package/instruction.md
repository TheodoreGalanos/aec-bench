You are a wastewater process engineer checking a task-owned synthetic SSC-10 instrumented process control and valve package.

Use only the task-owned synthetic source pack values shown below for numeric grading. P&ID review, control valve sizing, loop scaling, and control narrative workflows shape the context only; this instance does not parse a real P&ID, vendor export, or authority-approved design.

## Scene

- Product: `SSC-10-LH-04`
- P&ID: `PID-10-VALVE-04`
- Loop schedule: `LOOP-10-SCHED-04`
- Valve data sheet: `VALVE-10-DATA-04`
- Process range table: `RANGE-10-PV-04`
- Control narrative: `CONTROL-10-NARR-04`
- Instrumentation memo: `MEMO-10-INST-04`

## Source Values

| Item | Value |
| --- | --- |
| Design flow | {{ design_flow_l_s }} L/s |
| Specific gravity | {{ specific_gravity }} |
| Upstream pressure | {{ upstream_pressure_kpa }} kPa |
| Downstream pressure | {{ downstream_pressure_kpa }} kPa |
| Selected valve Cv | {{ selected_valve_cv }} |
| Total control-zone drop | {{ total_control_zone_drop_kpa }} kPa |
| Process LRV | {{ process_lrv }} |
| Process URV | {{ process_urv }} |
| Setpoint | {{ setpoint_value }} |
| Measured signal | {{ measured_signal_ma }} mA |
| Required fail-close time | {{ required_fail_close_s }} s |
| Actual fail-close time | {{ actual_fail_close_s }} s |
| Basin volume | {{ basin_volume_m3 }} m3 |

## Calculation Rules

- Required Cv equals `flow_gpm / sqrt(delta_psi / specific_gravity)`, where `flow_gpm = design_flow_l_s x 15.8503`.
- Valve authority equals valve pressure drop divided by total control-zone pressure drop.
- Command signal equals `4 + 16 x (setpoint - LRV) / (URV - LRV)`.
- Signal error equals the absolute difference between measured and calculated command signal.
- Fail-close margin equals required fail-close time minus actual fail-close time.
- Basin HRT equals basin volume divided by design flow, converted to hours.
- Overall pass score is `1.0` only when Cv margin, authority, signal error, fail-close margin, and HRT checks pass.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "required_cv": <numeric_value>,
  "cv_margin": <numeric_value>,
  "valve_authority_ratio": <numeric_value>,
  "command_signal_ma": <numeric_value>,
  "signal_error_ma": <numeric_value>,
  "fail_close_margin_s": <numeric_value>,
  "basin_hrt_hr": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
