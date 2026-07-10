You are a structural/facade engineer checking a task-owned synthetic SSC-09 facade pressure-zone difference and re-entrant geometry package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Facade pressure-zone redrawing, re-entrant corner review, support-point reassignment, and anchor-capacity workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-09-LH-06`
- Baseline elevation: `ELEV-09-BASE-06`
- Variant elevation: `ELEV-09-VARIANT-06`
- Pressure-zone schedule: `ZONE-09-SCHED-06`
- Support point register: `SUPPORT-09-POINTS-06`
- Anchor capacity note: `CAP-09-ANCHOR-06`
- Variant geometry memo: `MEMO-09-VARIANT-06`

## Source Values

| Item | Value |
|------|-------|
| Baseline corner-zone area | {{ baseline_corner_zone_area_m2 }} m2 |
| Variant corner-zone area | {{ variant_corner_zone_area_m2 }} m2 |
| Baseline corner pressure | {{ baseline_pressure_kpa }} kPa |
| Variant corner pressure | {{ variant_pressure_kpa }} kPa |
| Representative tributary area | {{ tributary_area_m2 }} m2 |
| Dead load | {{ dead_load_kpa }} kPa |
| Anchor tension capacity | {{ anchor_tension_capacity_kn }} kN |
| Anchor shear capacity | {{ anchor_shear_capacity_kn }} kN |
| Allowable utilization | {{ allowable_utilization }} |
| Support points reassigned | {{ support_points_reassigned }} |
| Support points required | {{ support_points_required }} |

## Checks

- Corner-zone area delta equals variant corner-zone area minus baseline corner-zone area.
- Corner-zone area delta percent equals area delta divided by baseline corner-zone area times 100.
- Pressure delta equals variant pressure minus baseline pressure.
- Baseline and variant corner loads equal pressure times representative tributary area.
- Dead load equals dead load pressure times representative tributary area.
- Baseline and variant utilization equal the square root of squared tension utilization plus squared shear utilization.
- Utilization margin equals allowable utilization minus variant utilization.
- Support reassignment fraction equals support points reassigned divided by support points required.
- Overall pass score is `1.0` only when the variant load increase is captured, utilization margin is non-negative, and all required supports are reassigned; otherwise it is `0.0`.

## Output Format

Write a compact facade geometry memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "corner_zone_area_delta_m2": <numeric_value>,
  "corner_zone_area_delta_percent": <numeric_value>,
  "pressure_delta_kpa": <numeric_value>,
  "baseline_corner_load_kn": <numeric_value>,
  "variant_corner_load_kn": <numeric_value>,
  "corner_load_delta_kn": <numeric_value>,
  "baseline_utilization": <numeric_value>,
  "variant_utilization": <numeric_value>,
  "utilization_delta": <numeric_value>,
  "utilization_margin": <numeric_value>,
  "support_reassignment_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
