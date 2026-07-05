You are a temporary works engineer checking a task-owned synthetic SSC-16 package for wind loading, temporary structural supports, ballast stability, and staging tolerance.

Use only the task-owned synthetic source pack values shown below for numeric grading. External AS/NZS 1170.2, temporary works, construction inspection, and staging workflows shape the context only; they are not extra data sources for this instance.

## Source Objects

- Product: `SSC-16-LH-02`
- Stage drawing: `STAGE-16-WIND-02`
- Temporary structure detail: `TEMP-16-STRUCT-02`
- Wind criteria: `WIND-16-CRIT-02`
- Support schedule: `SUPPORT-16-SCHED-02`
- Tolerance checklist: `TOL-16-CHECK-02`
- Temporary works memo: `MEMO-16-TEMPWORKS-02`

## Source Values

| Item | Value |
|------|-------|
| Regional wind speed | {{ regional_wind_speed_m_s }} m/s |
| Terrain multiplier | {{ terrain_multiplier }} |
| Direction multiplier | {{ direction_multiplier }} |
| Shielding multiplier | {{ shielding_multiplier }} |
| Air density | {{ air_density_kg_m3 }} kg/m3 |
| Force coefficient | {{ force_coefficient }} |
| Temporary panel area | {{ temporary_panel_area_m2 }} m2 |
| Anchor count | {{ anchor_count }} |
| Anchor load factor | {{ anchor_load_factor }} |
| Selected anchor capacity | {{ selected_anchor_capacity_kn }} kN |
| Wind centroid height | {{ wind_centroid_height_m }} m |
| Ballast weight | {{ ballast_weight_kn }} kN |
| Ballast arm | {{ ballast_arm_m }} m |
| Required stability ratio | {{ required_stability_ratio }} |
| Provided slot length | {{ provided_slot_length_mm }} mm |
| Required movement | {{ required_movement_mm }} mm |
| Allowed vertical tolerance | {{ allowed_vertical_tolerance_mm }} mm |
| Measured vertical tolerance | {{ measured_vertical_tolerance_mm }} mm |

## Required Checks

- Site wind speed equals regional wind speed times the three multipliers.
- Wind pressure equals `0.5 x air_density x site_wind_speed^2 / 1000`.
- Temporary panel wind force equals wind pressure times force coefficient times panel area.
- Anchor demand equals factored wind force divided by anchor count.
- Stability ratio equals ballast resisting moment divided by overturning moment.
- Slot and inspection margins are provided/allowed values minus required/measured values.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack, preserve the source object IDs above, and state whether the baseline checks pass.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "site_wind_speed_m_s": <numeric_value>,
  "wind_pressure_kpa": <numeric_value>,
  "temporary_panel_wind_force_kn": <numeric_value>,
  "anchor_demand_kn": <numeric_value>,
  "anchor_capacity_margin_kn": <numeric_value>,
  "overturning_moment_knm": <numeric_value>,
  "stability_ratio": <numeric_value>,
  "stability_margin": <numeric_value>,
  "slot_length_margin_mm": <numeric_value>,
  "inspection_tolerance_margin_mm": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
