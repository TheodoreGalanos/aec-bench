You are checking `SSC-18-LH-07`, a task-owned synthetic valve failure and safe-state repair package.

Use only the task-owned synthetic source pack values shown below for numeric grading. P&ID, valve datasheet, loop schedule, failure-mode table, and control narrative workflows shape the context only; this instance does not parse real P&IDs, PLC logic, trip matrices, or authority-approved repair records.

Source pack:

- P&ID: `PID-18-FAIL-07`
- Valve datasheet: `VDS-18-FAIL-07`
- Loop schedule: `LOOP-18-FAIL-07`
- Failure mode table: `MODE-18-FAIL-07`
- Control narrative: `NARR-18-SAFE-07`
- Repair response: `RESPONSE-18-FAIL-07`

Given values:

| Field | Value |
| --- | ---: |
| Failed signal | {{ failed_signal_ma }} mA |
| Fail threshold | {{ fail_threshold_ma }} mA |
| Fail-closed Cv / required safe Cv | {{ fail_closed_cv }} / {{ required_safe_cv }} |
| Bypass Cv / required bypass Cv | {{ bypass_cv }} / {{ required_bypass_cv }} |
| Safe flow / minimum safe flow | {{ safe_flow_m3_h }} / {{ minimum_safe_flow_m3_h }} m3/h |
| Tank volume / drawdown flow | {{ tank_volume_m3 }} m3 / {{ drawdown_flow_m3_h }} m3/h |
| Required safe duration | {{ required_safe_duration_h }} h |
| Source items resolved/total | {{ source_items_resolved }} / {{ source_items_total }} |
| Unresolved conflicts | {{ unresolved_conflict_count }} |

Required calculations:

- Failed signal margin equals fail threshold minus failed signal.
- Cv margins equal available Cv minus required Cv.
- Safe flow margin equals safe flow minus minimum safe flow.
- Safe runtime equals tank volume divided by drawdown flow.
- Source resolution fraction equals resolved source items divided by total source items.

Return one JSON object with keys:

```json
{
  "failed_signal_margin_ma": <numeric_value>,
  "fail_closed_cv_margin": <numeric_value>,
  "bypass_cv_margin": <numeric_value>,
  "safe_flow_margin_m3_h": <numeric_value>,
  "safe_runtime_h": <numeric_value>,
  "safe_runtime_margin_h": <numeric_value>,
  "source_resolution_fraction": <numeric_value>,
  "unresolved_conflict_count": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```

Do not claim authority approval, accepted project evidence, safety-case acceptance, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.
