You are a civil stormwater engineer checking a task-owned synthetic SSC-03 water-quality, pollutant-load, and construction sediment package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Construction sediment basin sizing, pollutant load estimation, temporary discharge review, and stormwater water-quality workflows shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-03-LH-06`
- Construction staging plan: `STAGE-SSC03-006`
- Catchment table: `CATCH-SSC03-006`
- Pollutant concentration basis: `POLLUT-SSC03-006`
- Sediment basin sketch: `BASIN-SSC03-006`
- Environmental control memo: `MEMO-SSC03-006`

## Source Values

| Item | Value |
|------|-------|
| Disturbed area | {{ disturbed_area_ha }} ha |
| Runoff depth | {{ runoff_depth_mm }} mm |
| Pollutant concentration | {{ pollutant_concentration_mg_l }} mg/L |
| Removal efficiency | {{ removal_efficiency }} |
| Sediment basin volume | {{ sediment_basin_volume_m3 }} m3 |
| Required volume per hectare | {{ required_volume_per_ha_m3 }} m3/ha |
| Dewatering flow | {{ dewatering_flow_l_s }} L/s |
| Temporary channel capacity | {{ temporary_channel_capacity_l_s }} L/s |
| Weir discharge coefficient | {{ weir_discharge_coefficient }} |
| Outlet weir length | {{ outlet_weir_length_m }} m |
| Outlet weir head | {{ outlet_weir_head_m }} m |
| Target capture | {{ target_capture_percent }} percent |

## Checks

- Runoff volume equals disturbed area times runoff depth.
- Pollutant load equals runoff volume times pollutant concentration with unit conversion.
- Required basin volume equals disturbed area times required volume per hectare.
- Overall pass score is `1.0` only when basin volume, temporary discharge, and capture checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated SWMM report-output evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "runoff_volume_m3": <numeric_value>,
  "pollutant_load_kg": <numeric_value>,
  "removed_load_kg": <numeric_value>,
  "residual_load_kg": <numeric_value>,
  "required_basin_volume_m3": <numeric_value>,
  "basin_volume_margin_m3": <numeric_value>,
  "temporary_discharge_margin_l_s": <numeric_value>,
  "weir_release_l_s": <numeric_value>,
  "capture_percent": <numeric_value>,
  "capture_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
