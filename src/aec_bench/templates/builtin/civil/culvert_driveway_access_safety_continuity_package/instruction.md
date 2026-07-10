You are a road drainage and access-safety engineer checking a task-owned synthetic SSC-01 culvert, driveway access, and safety continuity package.

Use only the task-owned synthetic source pack values below for numeric grading. Road access, culvert, freeboard, and sight-distance workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-01-LH-06`
- Driveway access profile: `ACCESS-SSC01-006`
- Culvert schedule: `CULV-SSC01-006`
- Tailwater table: `TAIL-SSC01-006`
- Sight-distance basis: `SIGHT-SSC01-006`
- Access safety memo: `MEMO-SSC01-006`

## Source Values

- Driveway low/high levels and length: {{ driveway_low_level_m }} m, {{ driveway_high_level_m }} m, {{ driveway_length_m }} m
- Allowable driveway grade: {{ allowable_driveway_grade_pct }} %
- Culvert diameter, Manning n, slope, and design flow: {{ culvert_diameter_m }} m, {{ culvert_mannings_n }}, {{ culvert_slope_pct }} %, {{ design_flow_m3_s }} m3/s
- Tailwater level, base headwater depth, headwater loss factor: {{ tailwater_level_m }} m, {{ headwater_base_depth_m }} m, {{ headwater_loss_factor_m }} m
- Road edge level and minimum freeboard: {{ road_edge_level_m }} m, {{ minimum_freeboard_m }} m
- Gutter flow, cross slope, longitudinal slope, gutter Manning n, allowable spread: {{ gutter_flow_m3_s }} m3/s, {{ cross_slope_pct }} %, {{ longitudinal_slope_pct }} %, {{ gutter_mannings_n }}, {{ allowable_spread_m }} m
- Access speed, reaction time, braking friction, grade, and available sight distance: {{ access_speed_kmh }} km/h, {{ sight_reaction_time_s }} s, {{ braking_friction_coefficient }}, {{ access_grade_pct }} %, {{ available_sight_distance_m }} m

## Required Calculations

- Driveway grade is the level difference divided by driveway length.
- Culvert full-flow capacity uses Manning's equation for a circular full pipe.
- Headwater level is tailwater plus base depth plus a ratio-squared loss allowance.
- Freeboard is road edge level minus headwater level.
- Roadway spread uses the triangular-gutter relation with SI coefficient `0.376`.
- Sight distance uses reaction distance plus grade-adjusted braking distance.
- Overall pass score is `1.0` only when grade, culvert, freeboard, spread, and sight-distance margins pass.

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state that the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "driveway_grade_percent": <numeric_value>,
  "driveway_grade_margin_percent": <numeric_value>,
  "culvert_capacity_m3_s": <numeric_value>,
  "culvert_capacity_margin_m3_s": <numeric_value>,
  "headwater_level_m": <numeric_value>,
  "freeboard_m": <numeric_value>,
  "freeboard_margin_m": <numeric_value>,
  "roadway_spread_m": <numeric_value>,
  "spread_margin_m": <numeric_value>,
  "sight_distance_required_m": <numeric_value>,
  "sight_distance_margin_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
