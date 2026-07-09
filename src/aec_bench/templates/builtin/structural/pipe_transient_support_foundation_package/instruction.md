You are a structural engineer checking a task-owned synthetic SSC-14 pipe transient support and foundation package for one anchored pipe bend, one concrete base, and one anchor group.

Use only the task-owned synthetic source pack values shown below for numeric grading. External ASME B31.3, ACI 318, AutoPIPE, and Terzaghi bearing-capacity routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Pipe alignment/P&ID: `PIPE-SSC14-001`
- Transient/thrust event table: `TRANS-14-001`
- Anchored support layout: `SUP-14-ANCH-01`
- Concrete foundation detail: `FDN-14-BASE-01`
- Load case schedule: `LC-14-ULS-01`
- Foundation soil note: `SOIL-14-BEAR-01`
- Anchor schedule: `ANCH-14-001`
- Support design memo: `MEMO-14-SUPPORT-01`

## Pipe Transient Basis

| Item | Value |
|------|-------|
| Controlling transient pressure | {{ transient_pressure_kpa }} kPa |
| Pipe internal diameter for transient thrust | {{ pipe_internal_diameter_mm }} mm |
| Anchored bend angle | {{ bend_angle_deg }} deg |

Transient checks:

- Pipe internal area equals `pi / 4 x (pipe_internal_diameter_mm / 1000)^2`.
- Pressure force equals `transient_pressure_kpa x pipe_internal_area_m2`.
- Transient thrust equals `2 x pressure_force_kn x sin(bend_angle_deg / 2)`.

## Support Dead-Load Basis

| Item | Value |
|------|-------|
| Pipe outside diameter | {{ pipe_outer_diameter_mm }} mm |
| Pipe wall thickness | {{ pipe_wall_thickness_mm }} mm |
| Steel density | {{ steel_density_kg_m3 }} kg/m3 |
| Contents density | {{ contents_density_kg_m3 }} kg/m3 |
| Insulation thickness | {{ insulation_thickness_mm }} mm |
| Insulation density | {{ insulation_density_kg_m3 }} kg/m3 |
| Tributary support span | {{ support_span_m }} m |
| Valve concentrated weight | {{ valve_weight_kn }} kN |
| Saddle and clamp weight | {{ saddle_weight_kn }} kN |

Support checks:

- Pipe dead-load inside diameter equals `pipe_outer_diameter_mm - 2 x pipe_wall_thickness_mm`.
- Steel area equals `pi / 4 x (outer_diameter^2 - inside_diameter^2)` using metres.
- Contents area equals `pi / 4 x inside_diameter^2` using metres.
- Insulation area equals `pi / 4 x (insulation_outer_diameter^2 - pipe_outer_diameter^2)` using metres.
- Each line load equals `area x density x 9.81 / 1000`.
- Operating line load equals steel, contents, and insulation line loads.
- Support vertical service reaction equals `operating_line_load_kn_m x support_span_m + valve_weight_kn + saddle_weight_kn`.

## Foundation, Bearing, Anchor, And Sliding Basis

| Item | Value |
|------|-------|
| Foundation length along thrust | {{ foundation_length_along_thrust_m }} m |
| Foundation transverse width | {{ foundation_width_transverse_m }} m |
| Foundation depth | {{ foundation_depth_m }} m |
| Concrete unit weight | {{ concrete_unit_weight_kn_m3 }} kN/m3 |
| Pipe centreline height above bearing plane | {{ pipe_centerline_height_m }} m |
| Vertical load factor | {{ vertical_load_factor }} |
| Horizontal transient load factor | {{ horizontal_load_factor }} |
| Soil cohesion | {{ cohesion_kpa }} kPa |
| Soil friction angle | {{ soil_friction_angle_deg }} deg |
| Soil unit weight | {{ soil_unit_weight_kn_m3 }} kN/m3 |
| Foundation embedment depth | {{ embedment_depth_m }} m |
| Terzaghi footing shape convention | {{ footing_shape }} |
| Water table depth below grade | {{ water_table_depth_m }} m |
| Bearing factor of safety | {{ bearing_factor_of_safety }} |
| Sliding friction coefficient | {{ sliding_friction_coefficient }} |
| Active anchor bolt count | {{ anchor_bolt_count }} |
| Allowable shear per anchor bolt | {{ anchor_allowable_shear_per_bolt_kn }} kN |

Foundation checks:

- Foundation self-weight equals `foundation_length_along_thrust_m x foundation_width_transverse_m x foundation_depth_m x concrete_unit_weight_kn_m3`.
- Terzaghi allowable bearing uses the source-owned strip footing convention with `Nc = 37.162`, `Nq = 22.456`, and `Ngamma = 19.7` for the 30 degree friction angle; use these exact factors for this synthetic source pack.
- Water table is below the failure zone, so `q = soil_unit_weight_kn_m3 x embedment_depth_m` and `gamma_eff = soil_unit_weight_kn_m3`.
- Ultimate bearing equals `cohesion_kpa x Nc x 1.0 + q x Nq + soil_unit_weight_kn_m3 x foundation_width_transverse_m x 0.5 x Ngamma`.
- Terzaghi allowable bearing equals `ultimate_bearing_capacity_kpa / bearing_factor_of_safety`.
- Factored vertical load equals `vertical_load_factor x (support_vertical_service_kn + foundation_self_weight_kn)`.
- Factored horizontal load equals `horizontal_load_factor x transient_thrust_kn`.
- Overturning moment equals `factored_horizontal_load_kn x pipe_centerline_height_m`.
- Bearing eccentricity equals `overturning_moment_knm / factored_vertical_load_kn`.
- Middle-third limit equals `foundation_length_along_thrust_m / 6`.
- Maximum bearing pressure equals `(factored_vertical_load_kn / base_area) x (1 + 6 x bearing_eccentricity_m / foundation_length_along_thrust_m)`.
- Bearing utilization equals maximum bearing pressure divided by Terzaghi allowable bearing.
- Anchor shear per bolt equals `factored_horizontal_load_kn / anchor_bolt_count`.
- Anchor shear utilization equals anchor shear per bolt divided by allowable shear per anchor bolt.
- Sliding margin equals `sliding_friction_coefficient x factored_vertical_load_kn - factored_horizontal_load_kn`.
- Overall pass score is `1.0` only when bearing eccentricity is within the middle third, bearing utilization is no greater than 1.0, anchor shear utilization is no greater than 1.0, and sliding margin is non-negative; otherwise it is `0.0`.

## Output Format

Write a compact support design memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pipe_internal_area_m2": <numeric_value>,
  "pressure_force_kn": <numeric_value>,
  "transient_thrust_kn": <numeric_value>,
  "operating_line_load_kn_m": <numeric_value>,
  "support_vertical_service_kn": <numeric_value>,
  "foundation_self_weight_kn": <numeric_value>,
  "terzaghi_allowable_bearing_kpa": <numeric_value>,
  "factored_vertical_load_kn": <numeric_value>,
  "factored_horizontal_load_kn": <numeric_value>,
  "overturning_moment_knm": <numeric_value>,
  "bearing_eccentricity_m": <numeric_value>,
  "middle_third_limit_m": <numeric_value>,
  "maximum_bearing_kpa": <numeric_value>,
  "bearing_utilization": <numeric_value>,
  "anchor_shear_per_bolt_kn": <numeric_value>,
  "anchor_shear_utilization": <numeric_value>,
  "sliding_margin_kn": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
