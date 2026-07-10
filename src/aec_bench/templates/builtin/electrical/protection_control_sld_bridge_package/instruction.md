You are checking `SSC-18-LH-03`, a task-owned synthetic protection and control setting bridge to SLD package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Protection-setting, SLD, CT, loop schedule, and fault-study workflows shape the context only; this instance does not parse a real SLD, relay file, fault model, or authority-approved setting sheet.

Source pack:

- Single-line diagram: `SLD-18-FEEDER-03`
- Protection setting table: `SET-18-PROT-03`
- Instrument transformer data: `CT-18-DATA-03`
- Loop schedule: `LOOP-18-SCHED-03`
- Fault/load table: `FAULT-18-TABLE-03`
- Control-setting memo: `MEMO-18-SET-03`

Given values:

| Field | Value |
| --- | ---: |
| Primary measurement current | {{ primary_current_a }} A |
| CT ratio | {{ ct_primary_a }}:{{ ct_secondary_a }} |
| Signal range | {{ lower_range_current_a }} to {{ upper_range_current_a }} A |
| Pickup current | {{ pickup_current_a }} A |
| Fault current | {{ fault_current_ka }} kA |
| Transformer ratio error | {{ transformer_ratio_error_pct }} percent |
| Feeder full-load current | {{ feeder_full_load_a }} A |
| Breaker trip setting | {{ breaker_trip_a }} A |

Required calculations:

- CT secondary current equals primary current divided by CT primary rating times CT secondary rating.
- 4-20 mA signal equals `4 + 16 x (current - lower range) / current span`.
- Pickup margin equals pickup current minus measured primary current.
- Fault pickup ratio equals fault current in amperes divided by pickup current.
- Feeder load margin equals breaker trip setting minus feeder full-load current.
- CT error current equals primary current times transformer ratio error percent.

Return one JSON object with keys:

```json
{
  "ct_secondary_current_a": <numeric_value>,
  "measurement_signal_ma": <numeric_value>,
  "pickup_signal_ma": <numeric_value>,
  "pickup_margin_a": <numeric_value>,
  "fault_pickup_ratio": <numeric_value>,
  "feeder_load_margin_a": <numeric_value>,
  "ct_error_current_a": <numeric_value>,
  "trip_signal_headroom_ma": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```

Do not claim authority approval, accepted project evidence, relay-file validity, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.
