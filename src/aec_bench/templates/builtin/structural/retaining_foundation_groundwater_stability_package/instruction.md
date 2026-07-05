You are a structural engineer checking a task-owned synthetic SSC-14 retaining/foundation groundwater and structural stability package.

Use only the task-owned synthetic source pack values below for numeric grading. Ground reports, retaining wall calculations, groundwater tables, and foundation checks shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-14-LH-04`
- Ground report: `GEO-SSC14-004`
- Wall section: `WALL-SSC14-004`
- Groundwater table: `GW-SSC14-004`
- Surcharge plan: `SUR-SSC14-004`
- Retaining interface memo: `MEMO-SSC14-004`

## Source Values

- Retained height, soil unit weight, and friction angle: {{ retained_height_m }} m, {{ soil_unit_weight_kn_m3 }} kN/m3, {{ soil_friction_angle_deg }} deg
- Surcharge and water height: {{ surcharge_kpa }} kPa and {{ water_height_m }} m
- Wall vertical weight, base width, and resisting lever arm ratio: {{ wall_vertical_weight_kn_m }} kN/m, {{ base_width_m }} m, {{ resisting_lever_arm_ratio }}
- Base friction coefficient and allowable bearing: {{ base_friction_coefficient }} and {{ allowable_bearing_kpa }} kPa
- Uplift force: {{ uplift_force_kn_m }} kN/m
- Minimum overturning and sliding factors of safety: {{ minimum_overturning_fs }} and {{ minimum_sliding_fs }}

## Required Calculations

- Rankine active coefficient is `tan(45 - phi / 2)^2`.
- Active earth force is `0.5 x Ka x gamma x H^2`.
- Surcharge force is `Ka x surcharge x H`.
- Hydrostatic force is `0.5 x 9.81 x water_height^2`.
- Overturning moment uses force resultants at `H/3`, `H/2`, and `water_height/3`.
- Resisting moment is wall vertical weight times base width times the resisting lever arm ratio.
- Sliding factor of safety is friction times net vertical weight divided by total lateral force.
- Bearing pressure is wall vertical weight divided by base width.
- Uplift margin is `0.9 x wall_vertical_weight - uplift_force`.
- Overall pass score is `1.0` only when overturning, sliding, bearing, and uplift checks pass.

Write a compact retaining interface memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "active_earth_force_kn_m": <numeric_value>,
  "surcharge_force_kn_m": <numeric_value>,
  "hydrostatic_force_kn_m": <numeric_value>,
  "total_lateral_force_kn_m": <numeric_value>,
  "overturning_moment_knm_m": <numeric_value>,
  "resisting_moment_knm_m": <numeric_value>,
  "overturning_factor_of_safety": <numeric_value>,
  "sliding_factor_of_safety": <numeric_value>,
  "bearing_pressure_kpa": <numeric_value>,
  "bearing_utilization": <numeric_value>,
  "uplift_margin_kn_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
