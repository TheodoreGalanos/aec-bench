You are a civil roof and envelope engineer checking a task-owned synthetic SSC-09 roof drainage, PV layout, and wind uplift package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Roof drainage, PV layout, wind uplift, and fixing workflows shape the context only; this instance does not run external software, parse real roof plans, or validate a standards clause.

## Scene

- Product: `SSC-09-LH-02`
- Roof catchment source: `ROOF-09-CATCH-02`
- PV layout: `PV-09-LAYOUT-02`
- Gutter/downpipe schedule: `GUTTER-09-SCHED-02`
- Wind uplift basis: `WIND-09-UPLIFT-02`
- PV fixing schedule: `FIX-09-PV-02`
- Roof/PV memo: `MEMO-09-ROOF-PV-02`

## Source Values

| Item | Value |
| --- | --- |
| Roof catchment area | {{ roof_catchment_area_m2 }} m2 |
| Rainfall intensity | {{ rainfall_intensity_mm_h }} mm/h |
| Runoff coefficient | {{ runoff_coefficient }} |
| Gutter capacity | {{ gutter_capacity_l_s }} L/s |
| Downpipe count | {{ downpipe_count }} |
| Downpipe capacity | {{ downpipe_capacity_l_s }} L/s |
| PV array area | {{ pv_array_area_m2 }} m2 |
| PV uplift pressure | {{ pv_uplift_pressure_kpa }} kPa |
| PV dead load | {{ pv_dead_load_kpa }} kPa |
| PV fixing capacity | {{ pv_fixing_capacity_kn }} kN |
| Drainage obstruction area | {{ drainage_obstruction_area_m2 }} m2 |
| Maximum drainage obstruction area | {{ max_drainage_obstruction_area_m2 }} m2 |

## Checks

- Roof runoff equals catchment area times rainfall intensity times runoff coefficient divided by 3600.
- Downpipe total capacity equals downpipe count times downpipe capacity.
- PV uplift force equals PV array area times uplift pressure.
- PV fixing margin equals fixing capacity minus uplift force.
- Drainage obstruction margin equals maximum obstruction area minus obstruction area.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "roof_runoff_l_s": <numeric_value>,
  "gutter_capacity_margin_l_s": <numeric_value>,
  "downpipe_total_capacity_l_s": <numeric_value>,
  "downpipe_capacity_margin_l_s": <numeric_value>,
  "pv_uplift_force_kn": <numeric_value>,
  "pv_dead_load_kn": <numeric_value>,
  "pv_fixing_margin_kn": <numeric_value>,
  "drainage_obstruction_margin_m2": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
