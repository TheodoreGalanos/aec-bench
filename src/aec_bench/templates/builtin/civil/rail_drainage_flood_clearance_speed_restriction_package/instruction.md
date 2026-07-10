You are a rail civil designer checking `SSC-02-LH-04`, a task-owned synthetic SSC-02 rail drainage, flood-clearance, and speed-restriction package.

Use only the task-owned synthetic source pack values below for numeric grading. Rail drainage and operating restriction workflows shape the context only; this instance does not run a hydraulic model, parse a real drainage long section, or validate an operator restriction.

## Scene

- Design case: `CASE-SSC02-FLOOD-04`
- Track and drainage long section: `TRACK-02-DRAIN-04`
- Culvert schedule: `CULVERT-02-SCHED-04`
- Flood level table: `FLOOD-02-LEVEL-04`
- Wayside equipment layout: `WAYSIDE-02-LAYOUT-04`
- Flood operating rule: `OPS-02-FLOOD-04`
- Flood resilience memo: `MEMO-02-FLOOD-04`

## Source Values

| Item | Value |
|------|-------|
| Catchment area | {{ catchment_area_ha }} ha |
| Rainfall intensity | {{ rainfall_intensity_mm_h }} mm/h |
| Runoff coefficient | {{ runoff_coefficient }} |
| Culvert capacity | {{ culvert_capacity_m3_s }} m^3/s |
| Track low-rail level | {{ track_low_rail_level_m }} m |
| Flood level | {{ flood_level_m }} m |
| Required freeboard | {{ required_freeboard_m }} m |
| Equipment plinth level | {{ equipment_plinth_level_m }} m |
| Minimum equipment clearance | {{ minimum_equipment_clearance_m }} m |
| Normal speed | {{ normal_speed_kmh }} km/h |
| Restricted speed | {{ restricted_speed_kmh }} km/h |

Checks:

- Peak flow equals `0.00278 x runoff_coefficient x rainfall_intensity x catchment_area`.
- Culvert capacity margin equals culvert capacity minus peak flow.
- Track freeboard equals low-rail level minus flood level.
- Equipment freeboard equals equipment plinth level minus flood level.
- Speed reduction equals normal speed minus restricted speed.
- Overall pass score is `1.0` only when culvert, track-freeboard, and equipment-exposure margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, hydraulic model validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "peak_flow_m3_s": <numeric_value>,
  "culvert_capacity_margin_m3_s": <numeric_value>,
  "track_freeboard_m": <numeric_value>,
  "freeboard_margin_m": <numeric_value>,
  "equipment_freeboard_m": <numeric_value>,
  "equipment_exposure_margin_m": <numeric_value>,
  "speed_reduction_kmh": <numeric_value>,
  "restriction_pass_score": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
