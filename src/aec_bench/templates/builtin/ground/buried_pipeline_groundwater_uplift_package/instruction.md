You are a ground and pipeline engineer checking a task-owned synthetic SSC-11 buried pipeline groundwater and uplift package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Buried pipeline flotation checks, seepage exit-gradient checks, pressure class coordination, and trench bedding workflows shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-11-LH-05`
- Pipeline profile: `PROFILE-SSC11-005`
- Geotechnical note: `GEO-SSC11-005`
- Pressure class note: `PRESS-SSC11-005`
- Bedding detail: `BED-SSC11-005`
- Coordination memo: `MEMO-SSC11-005`

## Source Values

| Item | Value |
|------|-------|
| Pipe outer diameter | {{ pipe_outer_diameter_m }} m |
| Pipe wall thickness | {{ pipe_wall_thickness_m }} m |
| Pipe unit weight | {{ pipe_unit_weight_kn_m3 }} kN/m3 |
| Water unit weight | {{ water_unit_weight_kn_m3 }} kN/m3 |
| Soil unit weight | {{ soil_unit_weight_kn_m3 }} kN/m3 |
| Soil cover | {{ soil_cover_m }} m |
| Trench width | {{ trench_width_m }} m |
| Bedding resistance | {{ bedding_resistance_kn_m }} kN/m |
| Groundwater head difference | {{ groundwater_head_difference_m }} m |
| Seepage path length | {{ seepage_path_length_m }} m |
| Critical exit gradient | {{ critical_exit_gradient }} |
| Required uplift factor of safety | {{ required_uplift_factor_of_safety }} |
| Required exit-gradient factor of safety | {{ required_exit_gradient_factor_of_safety }} |
| Operating pressure | {{ operating_pressure_kpa }} kPa |
| Pipe pressure class | {{ pipe_pressure_class_kpa }} kPa |

## Checks

- Buoyant uplift equals water unit weight times pipe outside displaced area.
- Pipe self-weight equals pipe unit weight times pipe annulus area.
- Contents weight equals water unit weight times pipe internal area.
- Soil overburden equals soil unit weight times cover times trench width.
- Downward resistance equals pipe self-weight, contents weight, soil overburden, and bedding resistance.
- Exit gradient equals groundwater head difference divided by seepage path length.
- Overall pass score is `1.0` only when uplift, exit-gradient, and pressure-class margins pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "buoyant_uplift_kn_m": <numeric_value>,
  "pipe_self_weight_kn_m": <numeric_value>,
  "contents_weight_kn_m": <numeric_value>,
  "soil_overburden_kn_m": <numeric_value>,
  "downward_resistance_kn_m": <numeric_value>,
  "uplift_factor_of_safety": <numeric_value>,
  "exit_gradient": <numeric_value>,
  "exit_gradient_factor_of_safety": <numeric_value>,
  "pressure_class_margin_kpa": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
