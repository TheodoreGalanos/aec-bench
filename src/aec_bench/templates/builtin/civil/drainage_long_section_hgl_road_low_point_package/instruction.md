You are a civil drainage engineer checking a task-owned synthetic SSC-03 drainage long-section, HGL, and road low-point package.

Use only the task-owned synthetic source pack values shown below for numeric grading. FHWA HEC-22, Manning drainage calculations, road low-point drainage review, and stormwater HGL workflows shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-03-LH-02`
- Road long section: `ROAD-SSC03-002`
- Drainage long section: `DRAIN-SSC03-002`
- Pit and pipe schedule: `PITPIPE-SSC03-002`
- HGL table: `HGL-SSC03-002`
- Low-point memo: `MEMO-SSC03-002`

## Source Values

| Item | Value |
|------|-------|
| Upstream invert | {{ upstream_invert_m }} m |
| Downstream invert | {{ downstream_invert_m }} m |
| Pipe length | {{ pipe_length_m }} m |
| Pipe diameter | {{ pipe_diameter_m }} m |
| Design flow | {{ design_flow_m3_s }} m3/s |
| Manning n | {{ manning_n }} |
| Downstream tailwater | {{ downstream_tailwater_m }} m |
| Minor loss coefficient | {{ minor_loss_coefficient }} |
| Road low-point level | {{ road_low_point_level_m }} m |
| Minimum freeboard | {{ minimum_freeboard_m }} m |
| Gutter approach flow | {{ gutter_approach_flow_m3_s }} m3/s |
| Roadway spread factor | {{ roadway_spread_factor }} |
| Allowable spread | {{ allowable_spread_m }} m |
| Equipment threshold level | {{ equipment_threshold_level_m }} m |

## Checks

- Pipe slope equals upstream invert minus downstream invert divided by pipe length.
- Manning capacity uses full-pipe area and hydraulic radius.
- Upstream HGL equals downstream tailwater plus friction and minor losses.
- Road low-point freeboard, roadway spread, and equipment freeboard must all remain positive.
- Overall pass score is `1.0` only when capacity, freeboard, spread, and equipment freeboard checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated SWMM report-output evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pipe_slope_percent": <numeric_value>,
  "pipe_velocity_m_s": <numeric_value>,
  "manning_capacity_m3_s": <numeric_value>,
  "capacity_margin_m3_s": <numeric_value>,
  "friction_loss_m": <numeric_value>,
  "minor_loss_m": <numeric_value>,
  "upstream_hgl_m": <numeric_value>,
  "low_point_freeboard_m": <numeric_value>,
  "freeboard_margin_m": <numeric_value>,
  "roadway_spread_m": <numeric_value>,
  "spread_margin_m": <numeric_value>,
  "equipment_freeboard_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
