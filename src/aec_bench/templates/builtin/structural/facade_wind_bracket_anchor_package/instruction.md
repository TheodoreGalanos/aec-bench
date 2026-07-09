You are a structural/facade engineer checking a task-owned synthetic SSC-09 facade wind, bracket, anchor, and tolerance package for one redrawn rainscreen elevation bay.

Use only the task-owned synthetic source pack values shown below for numeric grading. External EN 1991-1-4, ASCE 7, NVELOPE, PROFIS, Fixfast, Downer, and other rainscreen workflow routes shape the practice context only; they are not extra data sources for this instance.

## Scene

- Facade case ledger: `CASE-SSC09-FACADE-001`
- Redrawn facade elevation: `ELEV-09-REDRAWN-01`
- Wind criteria note: `WIND-09-CRIT-01`
- Facade pressure-zone schedule: `PRESS-09-ZONES-01`
- Bracket/support schedule: `SUP-09-BRACKET-01`
- Concrete anchor excerpt: `ANCH-09-CONC-01`
- Tolerance and setout note: `TOL-09-SETOUT-01`
- Facade fixing memo: `MEMO-09-FIXING-01`

The representative elevation bay has one body bracket row, one edge bracket row, and one corner bracket row. The bracket schedule has one fixed-point row for vertical dead load and two sliding-point rows for wind restraint and expansion. Preserve these fixed and sliding points in the memo.

Unit convention for this source pack:

- `kPa x m2 = kN` for these pressure-area load checks.
- All bracket and anchor demands and resistances below are in `kN`; do not convert them again before forming utilization ratios.
- Utilization ratios are dimensionless `kN / kN` values. For example, `2.16 kN / 2.8 kN` is about `0.77`, not `0.00077`.

## Wind And Pressure-Zone Basis

| Item | Value |
|------|-------|
| Basic wind speed | {{ basic_wind_speed_m_s }} m/s |
| Source-owned velocity pressure | {{ source_velocity_pressure_kpa }} kPa |
| Body-zone pressure coefficient magnitude | {{ body_pressure_coefficient }} |
| Edge-zone pressure coefficient magnitude | {{ edge_pressure_coefficient }} |
| Corner-zone pressure coefficient magnitude | {{ corner_pressure_coefficient }} |

Wind checks:

- Velocity pressure equals the `source_velocity_pressure_kpa` value from `WIND-09-CRIT-01`. The basic wind speed is retained as source context only for this synthetic instance.
- Body pressure equals `velocity_pressure_kpa x body_pressure_coefficient`.
- Edge pressure equals `velocity_pressure_kpa x edge_pressure_coefficient`.
- Corner pressure equals `velocity_pressure_kpa x corner_pressure_coefficient`.
- Use pressure magnitudes for the bracket and anchor demand checks. The redrawn source pack treats the governing facade action as suction, but grading uses positive demand magnitudes.

## Bracket And Anchor Basis

| Item | Value |
|------|-------|
| Bracket tributary width | {{ tributary_width_m }} m |
| Bracket tributary height | {{ tributary_height_m }} m |
| Facade dead load | {{ facade_dead_load_kpa }} kPa |
| Bracket horizontal resistance | {{ bracket_horizontal_resistance_kn }} kN |
| Bracket vertical resistance | {{ bracket_vertical_resistance_kn }} kN |
| Anchor tension resistance | {{ anchor_tension_resistance_kn }} kN |
| Anchor shear resistance | {{ anchor_shear_resistance_kn }} kN |
| Anchor embedment | {{ anchor_embedment_mm }} mm |
| Minimum anchor embedment | {{ minimum_anchor_embedment_mm }} mm |
| Corner anchor edge distance x | {{ corner_anchor_edge_distance_x_mm }} mm |
| Corner anchor edge distance y | {{ corner_anchor_edge_distance_y_mm }} mm |
| Minimum anchor edge distance | {{ minimum_anchor_edge_distance_mm }} mm |
| Corner nearest anchor spacing | {{ corner_nearest_anchor_spacing_mm }} mm |
| Minimum anchor spacing | {{ minimum_anchor_spacing_mm }} mm |

Bracket and anchor checks:

- Tributary area equals `tributary_width_m x tributary_height_m`.
- Zone wind load equals `zone_pressure_kpa x tributary_area_m2`.
- Dead load per bracket equals `facade_dead_load_kpa x tributary_area_m2`.
- The dead load result is already in `kN`; use it directly in vertical margin and anchor shear utilization checks.
- Corner bracket horizontal utilization equals `corner_wind_load_kn / bracket_horizontal_resistance_kn`.
- Corner bracket vertical utilization equals `dead_load_per_bracket_kn / bracket_vertical_resistance_kn`.
- Anchor tension utilization equals `zone_wind_load_kn / anchor_tension_resistance_kn`.
- Anchor shear utilization equals `dead_load_per_bracket_kn / anchor_shear_resistance_kn`.
- Combined anchor utilization equals `sqrt(anchor_tension_utilization^2 + anchor_shear_utilization^2)`.
- Governing utilization is the maximum of body anchor combined utilization, edge anchor combined utilization, corner anchor combined utilization, corner bracket horizontal utilization, and corner bracket vertical utilization.
- Anchor embedment margin equals `anchor_embedment_mm - minimum_anchor_embedment_mm`.
- Anchor edge margin equals `min(corner_anchor_edge_distance_x_mm, corner_anchor_edge_distance_y_mm) - minimum_anchor_edge_distance_mm`.
- Anchor spacing margin equals `corner_nearest_anchor_spacing_mm - minimum_anchor_spacing_mm`.

## Tolerance And Setout Basis

| Item | Value |
|------|-------|
| Nominal cavity depth | {{ nominal_cavity_depth_mm }} mm |
| Measured wall offset | {{ measured_wall_offset_mm }} mm |
| Minimum bracket projection | {{ minimum_bracket_projection_mm }} mm |
| Maximum bracket projection | {{ maximum_bracket_projection_mm }} mm |
| Required remaining tolerance allowance | {{ installation_tolerance_allowance_mm }} mm |
| Fixed-point rows | {{ fixed_point_count }} |
| Sliding-point rows | {{ sliding_point_count }} |

Tolerance checks:

- Required projection equals `nominal_cavity_depth_mm + measured_wall_offset_mm`.
- Projection margin equals the smaller of `required_projection_mm - minimum_bracket_projection_mm` and `maximum_bracket_projection_mm - required_projection_mm`.
- Fixed-point vertical margin equals `bracket_vertical_resistance_kn - dead_load_per_bracket_kn`.
- Governing row is the corner row when the corner combined anchor utilization controls the maximum utilization.
- Overall pass score is `1.0` only when governing utilization is no greater than 1.0, anchor embedment/edge/spacing margins are non-negative, projection margin is at least the required remaining tolerance allowance, fixed-point vertical margin is non-negative, and the corner row is governing; otherwise it is `0.0`.

## Output Format

Write a compact facade fixing memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "velocity_pressure_kpa": <numeric_value>,
  "body_pressure_kpa": <numeric_value>,
  "edge_pressure_kpa": <numeric_value>,
  "corner_pressure_kpa": <numeric_value>,
  "tributary_area_m2": <numeric_value>,
  "body_wind_load_kn": <numeric_value>,
  "edge_wind_load_kn": <numeric_value>,
  "corner_wind_load_kn": <numeric_value>,
  "dead_load_per_bracket_kn": <numeric_value>,
  "corner_bracket_horizontal_utilization": <numeric_value>,
  "corner_bracket_vertical_utilization": <numeric_value>,
  "body_anchor_combined_utilization": <numeric_value>,
  "edge_anchor_combined_utilization": <numeric_value>,
  "corner_anchor_combined_utilization": <numeric_value>,
  "governing_utilization": <numeric_value>,
  "anchor_embedment_margin_mm": <numeric_value>,
  "anchor_edge_margin_mm": <numeric_value>,
  "anchor_spacing_margin_mm": <numeric_value>,
  "required_projection_mm": <numeric_value>,
  "projection_margin_mm": <numeric_value>,
  "fixed_point_vertical_margin_kn": <numeric_value>,
  "governing_row_is_corner_score": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
