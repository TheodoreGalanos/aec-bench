You are a structural engineer checking a task-owned synthetic SSC-14 wind turbine or solar foundation package.

Use only the task-owned synthetic source pack values below for numeric grading. Wind criteria, solar racking load, foundation geometry, geotechnical checks, and anchor reports shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-14-LH-06`
- Array/turbine layout: `PV-SSC14-006`
- Wind criteria: `WIND-SSC14-006`
- Foundation detail: `FDN-SSC14-006`
- Geotechnical parameter table: `GEO-SSC14-006`
- Foundation memo: `MEMO-SSC14-006`

## Source Values

- Wind speed and pressure coefficient: {{ wind_speed_m_s }} m/s and {{ wind_pressure_coefficient }}
- Tributary array area and array dead load: {{ tributary_array_area_m2 }} m2 and {{ array_dead_load_kpa }} kPa
- Foundation length, width, depth, and concrete unit weight: {{ foundation_length_m }} m, {{ foundation_width_m }} m, {{ foundation_depth_m }} m, {{ concrete_unit_weight_kn_m3 }} kN/m3
- Allowable bearing and sliding friction coefficient: {{ allowable_bearing_kpa }} kPa and {{ sliding_friction_coefficient }}
- Horizontal shear factor: {{ horizontal_shear_factor }}
- Anchor count and tension capacity: {{ anchor_count }} and {{ anchor_tension_capacity_kn }} kN

## Required Calculations

- Velocity pressure is `0.613 x wind_speed^2 / 1000`.
- Array wind load is velocity pressure times pressure coefficient times tributary array area.
- Array dead load is dead-load pressure times tributary array area.
- Foundation self-weight is length times width times depth times concrete unit weight.
- Net uplift is array wind load minus array dead load and foundation self-weight.
- Uplift margin is anchor group capacity minus net uplift.
- Bearing pressure is array dead load plus foundation self-weight divided by foundation area.
- Sliding margin is frictional resistance minus horizontal shear.
- Anchor tension demand is positive net uplift divided by anchor count.
- Overall pass score is `1.0` only when uplift, bearing, sliding, and anchor tension checks pass.

Write a compact foundation memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "source_velocity_pressure_kpa": <numeric_value>,
  "array_wind_load_kn": <numeric_value>,
  "array_dead_load_kn": <numeric_value>,
  "foundation_self_weight_kn": <numeric_value>,
  "net_uplift_kn": <numeric_value>,
  "uplift_margin_kn": <numeric_value>,
  "bearing_pressure_kpa": <numeric_value>,
  "bearing_utilization": <numeric_value>,
  "horizontal_shear_kn": <numeric_value>,
  "sliding_margin_kn": <numeric_value>,
  "anchor_tension_per_anchor_kn": <numeric_value>,
  "anchor_tension_utilization": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
