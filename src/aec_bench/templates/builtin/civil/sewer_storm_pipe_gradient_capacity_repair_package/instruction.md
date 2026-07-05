You are a civil drainage engineer checking a task-owned synthetic SSC-03 sewer/storm pipe gradient and capacity repair package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Manning pipe capacity, pipe invert schedule review, storm pipe repair workflows, and gravity pipe velocity checks shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-03-LH-07`
- Pipe schedule: `PIPE-SSC03-007`
- Invert table: `INVERT-SSC03-007`
- Long section: `LONG-SSC03-007`
- Capacity criteria: `CRIT-SSC03-007`
- Network correction memo: `MEMO-SSC03-007`

## Source Values

| Item | Value |
|------|-------|
| Scheduled upstream invert | {{ scheduled_upstream_invert_m }} m |
| Scheduled downstream invert | {{ scheduled_downstream_invert_m }} m |
| Long-section downstream invert | {{ long_section_downstream_invert_m }} m |
| Pipe length | {{ pipe_length_m }} m |
| Pipe diameter | {{ pipe_diameter_m }} m |
| Manning n | {{ manning_n }} |
| Design flow | {{ design_flow_m3_s }} m3/s |
| Invert conflict tolerance | {{ invert_conflict_tolerance_m }} m |
| Surface level | {{ surface_level_m }} m |
| Pipe outer diameter | {{ pipe_outer_diameter_m }} m |
| Minimum cover | {{ minimum_cover_m }} m |
| Minimum velocity | {{ minimum_velocity_m_s }} m/s |
| Maximum velocity | {{ maximum_velocity_m_s }} m/s |

## Checks

- Scheduled slope uses scheduled upstream and downstream inverts.
- Long-section slope uses scheduled upstream invert and long-section downstream invert.
- Manning capacity uses full-pipe area, hydraulic radius, and scheduled slope.
- Overall pass score is `1.0` only when invert conflict, capacity, velocity, and cover checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated SWMM report-output evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "scheduled_slope_percent": <numeric_value>,
  "long_section_slope_percent": <numeric_value>,
  "invert_conflict_m": <numeric_value>,
  "manning_capacity_m3_s": <numeric_value>,
  "capacity_margin_m3_s": <numeric_value>,
  "flow_velocity_m_s": <numeric_value>,
  "velocity_low_margin_m_s": <numeric_value>,
  "velocity_high_margin_m_s": <numeric_value>,
  "pipe_crown_cover_m": <numeric_value>,
  "cover_margin_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
