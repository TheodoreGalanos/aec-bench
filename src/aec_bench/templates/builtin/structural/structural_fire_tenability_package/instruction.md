You are a structural fire engineer checking a task-owned synthetic SSC-19 structural fire and tenability package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Structural fire engineering, tenability, egress, and fire-alarm workflows shape the context only; this instance does not run FDS, Smokeview, evacuation software, a structural fire model, or a real source-pack parser.

## Scene

- Product: `SSC-19-LH-03`
- Fire strategy: `FIRE-19-STRAT-03`
- HRR design basis: `HRR-19-DESIGN-03`
- Steel member schedule: `STEEL-19-MEMBER-03`
- Tenability criteria: `TEN-19-CRIT-03`
- Egress and alarm basis: `EGRESS-19-ALARM-03`
- Fire engineering memo: `MEMO-19-FIRE-ENG-03`

## Source Values

| Item | Value |
| --- | --- |
| Fire growth alpha | {{ fire_growth_alpha_kw_s2 }} kW/s2 |
| Time to check | {{ time_to_check_s }} s |
| Maximum HRR | {{ max_hrr_kw }} kW |
| Fire duration | {{ fire_duration_min }} min |
| Structural load ratio | {{ structural_load_ratio }} |
| Steel temperature | {{ steel_temperature_c }} degC |
| Visibility constant | {{ visibility_constant }} |
| Smoke extinction coefficient | {{ smoke_extinction_coefficient_m1 }} 1/m |
| Required visibility | {{ required_visibility_m }} m |
| Available egress width | {{ available_egress_width_m }} m |
| Occupant load | {{ occupant_load }} |
| Egress width factor | {{ egress_width_factor_m_per_10_persons }} m/10 persons |
| NAC current | {{ nac_current_a }} A |
| NAC capacity | {{ nac_capacity_a }} A |

## Checks

- Design HRR equals `min(fire_growth_alpha_kw_s2 x time_to_check_s^2, max_hrr_kw)`.
- Fire energy equals design HRR times duration in seconds divided by 1000.
- Steel critical temperature equals `39.19 x ln(1 / structural_load_ratio - 1) + 482`.
- Visibility distance equals visibility constant divided by smoke extinction coefficient.
- Required egress width equals occupant load times egress width factor divided by 10.
- NAC current margin equals NAC capacity minus NAC current.
- Overall pass score is `1.0` only when steel, visibility, egress, and NAC margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated fire-model evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "design_hrr_kw": <numeric_value>,
  "fire_energy_mj": <numeric_value>,
  "steel_critical_temp_c": <numeric_value>,
  "steel_temperature_margin_c": <numeric_value>,
  "visibility_distance_m": <numeric_value>,
  "visibility_margin_m": <numeric_value>,
  "required_egress_width_m": <numeric_value>,
  "egress_width_margin_m": <numeric_value>,
  "nac_current_margin_a": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
