You are a construction stormwater engineer checking a task-owned synthetic SSC-16 package for sediment basin volume, overflow readiness, drawdown, pollutant load, and post-storm inspection timing.

Use only the task-owned synthetic source pack values shown below for numeric grading. External CGP/SWPPP, erosion-control, basin-readiness, and inspection workflows shape the context only; they are not extra data sources for this instance.

## Source Objects

- Product: `SSC-16-LH-05`
- Catchment and staging plan: `CATCH-16-STAGE-05`
- Storm event table: `STORM-16-EVENT-05`
- Basin detail: `BASIN-16-DETAIL-05`
- Inspection checklist: `INSP-16-CHECK-05`
- Discharge criterion: `DISCH-16-CRIT-05`
- Readiness memo: `MEMO-16-READY-05`

## Source Values

| Item | Value |
|------|-------|
| Catchment area | {{ catchment_area_ha }} ha |
| Storm depth | {{ storm_depth_mm }} mm |
| Runoff coefficient | {{ runoff_coefficient }} |
| Sediment storage allowance | {{ sediment_allowance_m3 }} m3 |
| Provided basin volume | {{ provided_basin_volume_m3 }} m3 |
| Weir coefficient | {{ weir_coefficient }} |
| Weir length | {{ weir_length_m }} m |
| Weir head | {{ weir_head_m }} m |
| Peak inflow | {{ peak_inflow_m3_s }} m3/s |
| Provided freeboard | {{ provided_freeboard_m }} m |
| Required freeboard | {{ required_freeboard_m }} m |
| Outlet drawdown flow | {{ outlet_drawdown_flow_m3_s }} m3/s |
| Maximum drawdown time | {{ maximum_drawdown_time_h }} h |
| TSS event mean concentration | {{ tss_event_mean_concentration_mg_l }} mg/L |
| Inspection due window | {{ inspection_due_window_h }} h |
| Hours since storm end | {{ hours_since_storm_end }} h |

## Required Checks

- Runoff volume equals catchment area times storm depth times runoff coefficient.
- Required basin volume equals runoff volume plus sediment allowance.
- Weir capacity equals source-owned coefficient times length times head to the 1.5 power.
- Drawdown time equals required basin volume divided by outlet drawdown flow.
- TSS load uses runoff volume and event mean concentration.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack, preserve the source object IDs above, and state whether the baseline checks pass.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "runoff_volume_m3": <numeric_value>,
  "required_basin_volume_m3": <numeric_value>,
  "basin_headroom_m3": <numeric_value>,
  "weir_capacity_m3_s": <numeric_value>,
  "weir_capacity_margin_m3_s": <numeric_value>,
  "freeboard_margin_m": <numeric_value>,
  "drawdown_time_h": <numeric_value>,
  "drawdown_margin_h": <numeric_value>,
  "tss_load_kg": <numeric_value>,
  "inspection_window_margin_h": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
