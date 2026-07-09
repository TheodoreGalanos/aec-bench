You are checking a task-owned synthetic SSC-07 retaining wall seepage, uplift, and foundation package for `SSC-07-LH-02`.

Use only the task-owned synthetic source pack values shown below for numeric grading.

## Source Pack

- Wall section: `RET-07-WALL-01`
- Geotechnical report: `GEO-07-RET-01`
- Groundwater table: `GW-07-RET-01`
- Surcharge plan: `SUR-07-RET-01`
- Retaining design memo: `MEMO-07-RET-01`

## Source Values

| Item | Value |
|---|---:|
| Retained height | {{ retained_height_m }} m |
| Soil unit weight | {{ soil_unit_weight_kn_m3 }} kN/m3 |
| Friction angle | {{ friction_angle_deg }} degrees |
| Surcharge | {{ surcharge_kpa }} kPa |
| Base width | {{ base_width_m }} m |
| Wall weight | {{ wall_weight_kn_m }} kN/m |
| Base friction coefficient | {{ base_friction_coefficient }} |
| Passive resistance | {{ passive_resistance_kn_m }} kN/m |
| Allowable bearing | {{ allowable_bearing_kpa }} kPa |
| Head difference | {{ head_difference_m }} m |
| Seepage path | {{ seepage_path_m }} m |
| Critical gradient | {{ critical_gradient }} |

Compute:

- active pressure coefficient as `tan(45 - phi/2)^2`;
- active thrust as triangular soil thrust plus surcharge thrust;
- sliding and overturning factors of safety;
- maximum bearing pressure and bearing margin;
- exit gradient and exit-gradient factor of safety;
- uplift pressure and uplift margin.

Write a compact source-bound retaining design memo to `/workspace/output.md`. Preserve the source IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "active_pressure_coefficient": <numeric_value>,
  "active_thrust_kn_m": <numeric_value>,
  "sliding_fs": <numeric_value>,
  "overturning_fs": <numeric_value>,
  "max_bearing_pressure_kpa": <numeric_value>,
  "bearing_margin_kpa": <numeric_value>,
  "exit_gradient": <numeric_value>,
  "exit_gradient_fs": <numeric_value>,
  "uplift_pressure_kpa": <numeric_value>,
  "uplift_margin_kpa": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
