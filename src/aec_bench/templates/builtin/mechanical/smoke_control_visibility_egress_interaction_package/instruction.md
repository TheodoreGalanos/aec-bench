You are a mechanical/life-safety engineer checking a task-owned synthetic SSC-08 smoke control, visibility, and egress interaction package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External smoke-control, visibility, egress, alarm load, and battery-runtime workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-08-LH-05`
- Fire strategy: `FIRE-08-STRATEGY-05`
- Population schedule: `POP-08-SCHED-05`
- Ventilation schedule: `VENT-08-SCHED-05`
- Egress plan: `EGRESS-08-PLAN-05`
- Visibility criterion: `VIS-08-CRIT-05`
- Tenability memo: `MEMO-08-TENABILITY-05`

## Source Values

| Item | Value |
|------|-------|
| Fire zone volume | {{ fire_zone_volume_m3 }} m3 |
| Smoke exhaust flow | {{ smoke_exhaust_flow_m3_h }} m3/h |
| Required air changes | {{ required_air_changes_per_h }} 1/h |
| Smoke layer height | {{ smoke_layer_height_m }} m |
| Minimum smoke layer height | {{ minimum_smoke_layer_height_m }} m |
| Visibility | {{ visibility_m }} m |
| Required visibility | {{ required_visibility_m }} m |
| Population | {{ population_persons }} persons |
| Egress width factor | {{ egress_width_factor_mm_per_person }} mm/person |
| Provided egress width | {{ provided_egress_width_mm }} mm |
| Egress flow rate | {{ egress_flow_rate_person_m_s }} persons/(m*s) |
| Maximum egress time | {{ max_egress_time_s }} s |
| Ventilation load | {{ ventilation_load_kw }} kW |
| Alarm load | {{ alarm_load_kw }} kW |
| Battery capacity | {{ battery_capacity_kwh }} kWh |
| Battery usable fraction | {{ battery_usable_fraction }} |
| Required runtime | {{ required_runtime_h }} h |

## Checks

- Smoke exhaust air changes per hour equal smoke exhaust flow divided by fire zone volume.
- ACH margin equals exhaust ACH minus required ACH.
- Smoke layer height margin equals smoke layer height minus minimum smoke layer height.
- Visibility margin equals visibility minus required visibility.
- Required egress width equals population times egress width factor.
- Egress flow time equals population divided by provided width and egress flow rate.
- Battery margin equals usable battery capacity minus ventilation and alarm load energy for the required runtime.
- Overall pass score is `1.0` only when smoke, visibility, egress, and battery checks pass; otherwise it is `0.0`.

## Output Format

Write a compact tenability memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "smoke_exhaust_air_changes_per_h": <numeric_value>,
  "ach_margin": <numeric_value>,
  "smoke_layer_height_margin_m": <numeric_value>,
  "visibility_margin_m": <numeric_value>,
  "required_egress_width_mm": <numeric_value>,
  "egress_width_margin_mm": <numeric_value>,
  "egress_flow_time_s": <numeric_value>,
  "egress_time_margin_s": <numeric_value>,
  "life_safety_battery_margin_kwh": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
