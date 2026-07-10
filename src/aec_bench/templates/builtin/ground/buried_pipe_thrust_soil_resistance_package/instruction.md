You are checking a task-owned synthetic SSC-07 buried pipe, thrust block, and soil resistance package for `SSC-07-LH-07`.

Use only the task-owned synthetic source pack values shown below for numeric grading.

## Source Pack

- Pipe alignment: `PIPE-07-ALIGN-01`
- Transient/thrust event table: `TRANS-07-THRUST-01`
- Soil profile: `SOIL-07-PIPE-01`
- Thrust block detail: `TBLOCK-07-01`
- Buried-pipe support memo: `MEMO-07-PIPE-01`

## Source Values

| Item | Value |
|---|---:|
| Pipe diameter | {{ pipe_diameter_m }} m |
| Transient pressure | {{ transient_pressure_kpa }} kPa |
| Bend angle | {{ bend_angle_deg }} degrees |
| Passive resistance | {{ passive_resistance_kn }} kN |
| Thrust block vertical load | {{ thrust_block_vertical_load_kn }} kN |
| Thrust block base area | {{ thrust_block_base_area_m2 }} m2 |
| Allowable bearing | {{ allowable_bearing_kpa }} kPa |
| Groundwater head | {{ groundwater_head_m }} m |
| Cover resisting pressure | {{ cover_resisting_pressure_kpa }} kPa |
| Pipe length | {{ pipe_length_m }} m |
| Flow | {{ flow_m3_s }} m3/s |
| Hazen-Williams C | {{ hazen_williams_c }} |

Compute pipe internal area, transient thrust, thrust resistance margin, thrust utilization, bearing pressure and margin, uplift pressure and margin, Hazen-Williams headloss, and overall pass score.

Write a compact source-bound buried-pipe support memo to `/workspace/output.md`. Preserve the source IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pipe_internal_area_m2": <numeric_value>,
  "transient_thrust_kn": <numeric_value>,
  "thrust_resistance_margin_kn": <numeric_value>,
  "thrust_utilization": <numeric_value>,
  "bearing_pressure_kpa": <numeric_value>,
  "bearing_margin_kpa": <numeric_value>,
  "uplift_pressure_kpa": <numeric_value>,
  "uplift_margin_kpa": <numeric_value>,
  "hazen_williams_headloss_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
