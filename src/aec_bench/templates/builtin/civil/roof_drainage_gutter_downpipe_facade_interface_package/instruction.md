You are a civil roof drainage engineer checking a task-owned synthetic roof drainage, gutter/downpipe, and facade interface package.

Use only the task-owned synthetic source pack values shown below for numeric grading. AS/NZS 3500.3-style roof drainage workflows, gutter and downpipe sizing, roof overflow review, and facade interface coordination shape the workflow context only; they are not extra data sources for this instance.

## Scene

- SSC-03 product family: `SSC-03-LH-04`
- SSC-03 roof catchment markup: `ROOF-SSC03-004`
- SSC-03 gutter and downpipe schedule: `GUTTER-SSC03-004`
- SSC-03 facade/parapet section: `FACADE-SSC03-004`
- SSC-03 rainfall table: `RAIN-SSC03-004`
- SSC-03 roof drainage memo: `MEMO-SSC03-004`
- SSC-09 product family: `SSC-09-LH-07`
- SSC-09 roof fall plan: `ROOF-09-FALL-07`
- SSC-09 gutter repair schedule: `GUTTER-09-REPAIR-07`
- SSC-09 downpipe schedule: `DOWNPIPE-09-SCHED-07`
- SSC-09 overflow sketch: `OVERFLOW-09-SKETCH-07`
- SSC-09 facade/equipment exposure note: `FACADE-09-EXPOSE-07`
- SSC-09 repair memo: `MEMO-09-REPAIR-07`

## Source Values

| Item | Value |
|------|-------|
| Roof catchment area | {{ roof_catchment_area_m2 }} m2 |
| Rainfall intensity | {{ rainfall_intensity_mm_h }} mm/h |
| Runoff coefficient | {{ runoff_coefficient }} |
| Gutter capacity | {{ gutter_capacity_l_s }} L/s |
| Downpipe count | {{ downpipe_count }} |
| Downpipe capacity | {{ downpipe_capacity_l_s }} L/s |
| Overflow weir coefficient | {{ overflow_weir_coefficient }} |
| Overflow weir length | {{ overflow_weir_length_m }} m |
| Overflow head | {{ overflow_head_m }} m |
| Parapet freeboard | {{ parapet_freeboard_m }} m |
| Minimum freeboard | {{ minimum_freeboard_m }} m |
| Facade zone pressure | {{ facade_zone_pressure_kpa }} kPa |
| Fixing allowable pressure | {{ fixing_allowable_pressure_kpa }} kPa |

## Checks

- Roof runoff equals area times rainfall intensity times runoff coefficient divided by 3600.
- Downpipe capacity equals downpipe count times capacity per downpipe.
- Overflow capacity equals source-owned coefficient times length times head to the power 1.5.
- Overall pass score is `1.0` only when gutter, downpipe, overflow, freeboard, and facade fixing checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated SWMM report-output evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "roof_runoff_l_s": <numeric_value>,
  "gutter_capacity_margin_l_s": <numeric_value>,
  "downpipe_total_capacity_l_s": <numeric_value>,
  "downpipe_capacity_margin_l_s": <numeric_value>,
  "overflow_capacity_l_s": <numeric_value>,
  "overflow_capacity_margin_l_s": <numeric_value>,
  "freeboard_margin_m": <numeric_value>,
  "facade_fixing_pressure_margin_kpa": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
