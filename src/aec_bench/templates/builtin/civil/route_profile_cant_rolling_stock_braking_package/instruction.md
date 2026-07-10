You are a rail alignment designer checking `SSC-02-LH-05`, a task-owned synthetic SSC-02 route profile, cant, and rolling-stock braking package.

Use only the task-owned synthetic source pack values below for numeric grading. Rail alignment, cant, and rolling-stock braking workflows shape the context only; this instance does not run track design software, parse a real alignment model, or validate an operator standard.

## Scene

- Design case: `CASE-SSC02-ALIGN-05`
- Alignment plan/profile: `ALIGN-02-PROFILE-05`
- Cant table: `CANT-02-TABLE-05`
- Rolling-stock data: `ROLL-02-DATA-05`
- Comfort criterion: `CRIT-02-COMFORT-05`
- Operations scenario: `OPS-02-SCENARIO-05`
- Alignment operations memo: `MEMO-02-ALIGN-05`

## Source Values

| Item | Value |
|------|-------|
| Curve radius | {{ curve_radius_m }} m |
| Operating speed | {{ speed_kmh }} km/h |
| Gauge | {{ gauge_m }} m |
| Applied cant | {{ applied_cant_mm }} mm |
| Maximum cant deficiency | {{ max_cant_deficiency_mm }} mm |
| Transition length | {{ transition_length_m }} m |
| Cant gradient limit | {{ cant_gradient_limit_mm_per_m }} mm/m |
| Vertical curve radius | {{ vertical_curve_radius_m }} m |
| Grade change | {{ grade_change_percent }} % |
| Braking rate | {{ braking_rate_m_s2 }} m/s^2 |
| Reaction time | {{ reaction_time_s }} s |
| Adverse grade | {{ grade_percent }} % |
| Davis A | {{ davis_a_n_per_t }} N/t |
| Davis B | {{ davis_b_n_per_t_kmh }} N/t/km/h |
| Davis C | {{ davis_c_n_per_t_kmh2 }} N/t/(km/h)^2 |
| Train mass | {{ train_mass_t }} t |

Checks:

- Equilibrium cant equals `gauge_m x 1000 x speed_m_s^2 / (9.81 x curve_radius_m)`.
- Cant deficiency equals equilibrium cant minus applied cant.
- Cant gradient equals applied cant divided by transition length.
- Vertical curve length equals vertical curve radius times grade change divided by 100.
- Braking distance uses the grade-adjusted braking deceleration.
- Overall pass score is `1.0` only when cant-deficiency, cant-gradient, and braking deceleration checks have non-negative margins; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, track-design software validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "speed_m_s": <numeric_value>,
  "equilibrium_cant_mm": <numeric_value>,
  "cant_deficiency_mm": <numeric_value>,
  "cant_deficiency_margin_mm": <numeric_value>,
  "cant_gradient_mm_per_m": <numeric_value>,
  "cant_gradient_margin_mm_per_m": <numeric_value>,
  "vertical_curve_length_m": <numeric_value>,
  "effective_braking_deceleration_m_s2": <numeric_value>,
  "braking_distance_m": <numeric_value>,
  "davis_resistance_n_per_t": <numeric_value>,
  "resistance_force_kn": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
