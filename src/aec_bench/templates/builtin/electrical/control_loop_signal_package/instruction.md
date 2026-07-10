You are an instrumentation and controls engineer checking a task-owned synthetic SSC-18 loop package for one valve, process value, 4-20 mA signal range, and alarm/trip handoff.

Use only the task-owned synthetic source pack values shown below for numeric grading. External ISA-5, ISA-75, ISA-84, Siemens TIA Portal, Rockwell Studio 5000, and Endress+Hauser routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Operating case: `OP-SSC18-LOOP-001`
- P&ID sheet: `PID-18-101`
- Loop controller: `FIC-18-101`
- Flow transmitter: `FIT-18-101`
- Control valve: `FCV-18-101`
- Valve datasheet: `VDS-18-FCV-101`
- Loop sheet: `LS-18-FIC-101`
- Control narrative: `CN-18-001`
- Alarm register: `ALM-18-FLOW-101`
- Commissioning record: `COM-18-LOOP-101`
- Loop memo: `MEMO-18-LOOP-001`

## Valve And Process Basis

| Item | Value |
|------|-------|
| Flow rate through FCV-18-101 | {{ flow_rate_m3_h }} m3/h |
| Upstream pressure | {{ upstream_pressure_bar }} bar |
| Downstream pressure | {{ downstream_pressure_bar }} bar |
| Fluid specific gravity | {{ fluid_specific_gravity }} |
| Fluid vapor pressure | {{ fluid_vapor_pressure_bar }} bar |
| Fluid critical pressure | {{ fluid_critical_pressure_bar }} bar |
| Valve liquid pressure recovery factor, FL | {{ fl_recovery_factor }} |
| Selected valve Cv | {{ selected_valve_cv }} |

Valve checks:

- Pressure drop equals upstream pressure minus downstream pressure.
- Liquid critical pressure ratio factor equals `0.96 - 0.28 x sqrt(fluid_vapor_pressure_bar / fluid_critical_pressure_bar)`.
- Choked pressure drop equals `FL^2 x (upstream_pressure_bar - liquid_critical_pressure_ratio_factor x fluid_vapor_pressure_bar)`.
- Effective pressure drop is the smaller of actual pressure drop and choked pressure drop.
- Required Cv equals `1.156 x flow_rate_m3_h x sqrt(fluid_specific_gravity / effective_pressure_drop_bar)`.
- Selected Cv headroom equals selected valve Cv minus required Cv.
- Valve travel percent equals required Cv divided by selected valve Cv, multiplied by 100.

## Loop Signal And Alarm Basis

| Item | Value |
|------|-------|
| Current process value at FIT-18-101 | {{ process_value_m3_h }} m3/h |
| Lower range value | {{ lower_range_value_m3_h }} m3/h |
| Upper range value | {{ upper_range_value_m3_h }} m3/h |
| High alarm setpoint | {{ high_alarm_flow_m3_h }} m3/h |
| High-high trip setpoint | {{ high_high_trip_flow_m3_h }} m3/h |

Signal checks:

- Span percent equals `(process_value_m3_h - lower_range_value_m3_h) / (upper_range_value_m3_h - lower_range_value_m3_h) x 100`.
- Current signal equals `4 + 16 x span_fraction`.
- Reconstructed process value equals `lower_range_value_m3_h + (current_signal_ma - 4) / 16 x range_span`.
- High alarm and high-high trip currents use the same 4-20 mA range.
- Alarm current headroom equals high alarm current minus current signal.
- Trip flow headroom equals high-high trip setpoint minus current process value.
- Overall pass score is `1.0` only when selected Cv headroom, alarm current headroom, and trip flow headroom are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pressure_drop_bar": <numeric_value>,
  "choked_pressure_drop_bar": <numeric_value>,
  "cv_required": <numeric_value>,
  "selected_cv_headroom": <numeric_value>,
  "valve_travel_pct": <numeric_value>,
  "span_pct": <numeric_value>,
  "current_signal_ma": <numeric_value>,
  "reconstructed_process_value": <numeric_value>,
  "high_alarm_current_ma": <numeric_value>,
  "high_high_trip_current_ma": <numeric_value>,
  "alarm_current_headroom_ma": <numeric_value>,
  "trip_flow_headroom_m3_h": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
