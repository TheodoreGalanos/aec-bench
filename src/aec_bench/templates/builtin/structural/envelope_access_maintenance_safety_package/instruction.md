You are a facade access and structural engineer checking a task-owned synthetic SSC-09 envelope access, maintenance, and safety package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Envelope access, maintenance loading, wind exposure, fall-arrest, and tolerance workflows shape the context only; this instance does not parse real access drawings, validate a safety certification, or prove authority approval.

## Scene

- Product: `SSC-09-LH-03`
- Access plan: `ACCESS-09-PLAN-03`
- Maintenance load schedule: `LOAD-09-MAINT-03`
- Weather criterion: `WIND-09-WEATHER-03`
- Access anchor schedule: `ANCH-09-ACCESS-03`
- Maintenance operations note: `OPS-09-MAINT-03`
- Maintenance safety memo: `MEMO-09-SAFETY-03`

## Source Values

| Item | Value |
| --- | --- |
| Access platform area | {{ access_platform_area_m2 }} m2 |
| Maintenance live load | {{ maintenance_live_load_kpa }} kPa |
| Access support capacity | {{ access_support_capacity_kn }} kN |
| Wind pressure | {{ wind_pressure_kpa }} kPa |
| Wind screen area | {{ wind_screen_area_m2 }} m2 |
| Wind anchor capacity | {{ wind_anchor_capacity_kn }} kN |
| Fall-arrest user count | {{ fall_arrest_user_count }} |
| Fall-arrest load per user | {{ fall_arrest_load_kn_per_user }} kN |
| Fall-arrest anchor capacity | {{ fall_arrest_anchor_capacity_kn }} kN |
| Access clear width | {{ access_clear_width_m }} m |
| Required access width | {{ required_access_width_m }} m |
| Measured tolerance gap | {{ measured_tolerance_gap_mm }} mm |
| Allowable tolerance gap | {{ allowable_tolerance_gap_mm }} mm |

## Checks

- Maintenance live load equals platform area times live load.
- Wind screen load equals wind pressure times exposed screen area.
- Fall-arrest demand equals user count times load per user.
- Access width margin equals clear width minus required width.
- Tolerance margin equals allowable gap minus measured gap.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, safety certification validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "maintenance_live_load_kn": <numeric_value>,
  "maintenance_load_margin_kn": <numeric_value>,
  "wind_screen_load_kn": <numeric_value>,
  "wind_anchor_margin_kn": <numeric_value>,
  "fall_arrest_demand_kn": <numeric_value>,
  "fall_arrest_margin_kn": <numeric_value>,
  "access_width_margin_m": <numeric_value>,
  "tolerance_margin_mm": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
