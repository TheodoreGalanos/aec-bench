You are checking `SSC-18-LH-04`, a task-owned synthetic commissioning and calibration review packet.

Use only the task-owned synthetic source pack values shown below for numeric grading. Commissioning, calibration, loop test, valve datasheet, and process-acceptance workflows shape the context only; this instance does not parse real commissioning records, calibration sheets, vendor exports, or authority-approved acceptance records.

Source pack:

- Commissioning checklist: `CHECK-18-COMM-04`
- Calibration sheet: `CAL-18-SHEET-04`
- Valve datasheet: `VDS-18-FCV-04`
- Loop schedule: `LOOP-18-SCHED-04`
- Process acceptance criteria: `CRIT-18-ACCEPT-04`
- Commissioning response: `RESPONSE-18-COMM-04`

Given values:

| Field | Value |
| --- | ---: |
| Test process value | {{ test_process_value_m3_h }} m3/h |
| Range | {{ lower_range_value_m3_h }} to {{ upper_range_value_m3_h }} m3/h |
| As-found signal | {{ as_found_signal_ma }} mA |
| Calibration tolerance | {{ calibration_tolerance_ma }} mA |
| Loop points passed/total | {{ loop_points_passed }} / {{ loop_points_total }} |
| Failed points | {{ failed_point_count }} |
| Process acceptance margin | {{ process_acceptance_margin }} |
| Required/selected valve Cv | {{ required_valve_cv }} / {{ selected_valve_cv }} |

Required calculations:

- Ideal signal equals `4 + 16 x (test value - lower range) / span`.
- Calibration error equals as-found signal minus ideal signal.
- Calibration error percent span equals absolute calibration error divided by 16 mA times 100.
- Calibration margin equals tolerance minus absolute calibration error.
- Loop-check pass fraction equals passed points divided by total points.
- Valve Cv headroom equals selected Cv minus required Cv.

Return one JSON object with keys:

```json
{
  "ideal_signal_ma": <numeric_value>,
  "calibration_error_ma": <numeric_value>,
  "calibration_error_pct_span": <numeric_value>,
  "calibration_margin_ma": <numeric_value>,
  "loop_check_pass_fraction": <numeric_value>,
  "failed_point_count": <numeric_value>,
  "process_acceptance_margin": <numeric_value>,
  "valve_cv_headroom": <numeric_value>,
  "commissioning_completeness_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```

Do not claim authority approval, accepted project evidence, commissioning acceptance, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.
