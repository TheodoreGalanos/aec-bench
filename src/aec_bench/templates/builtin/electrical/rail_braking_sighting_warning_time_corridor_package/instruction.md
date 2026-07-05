You are a rail signalling design engineer checking `SSC-02-LH-01`, a task-owned synthetic SSC-02 rail braking, sighting, and warning-time corridor package.

Use only the task-owned synthetic source pack values below for numeric grading. Braking, sighting, and operator warning-time workflows shape the context only; this instance does not run signalling software, parse a real route profile, or validate an operator standard.

## Scene

- Design case: `CASE-SSC02-BRAKE-01`
- Route profile: `ROUTE-02-PROFILE-01`
- Rolling-stock data: `ROLL-02-DATA-01`
- Signal layout: `SIG-02-LAYOUT-01`
- Sighting note: `SIGHT-02-NOTE-01`
- Operating rule: `RULE-02-OPS-01`
- Operations memo: `MEMO-02-BRAKE-01`

## Source Values

| Item | Value |
|------|-------|
| Train speed | {{ train_speed_kmh }} km/h |
| Adverse grade | {{ grade_percent }} % |
| Reaction time | {{ reaction_time_s }} s |
| Braking rate | {{ braking_rate_m_s2 }} m/s^2 |
| Davis A | {{ davis_a_n_per_t }} N/t |
| Davis B | {{ davis_b_n_per_t_kmh }} N/t/km/h |
| Davis C | {{ davis_c_n_per_t_kmh2 }} N/t/(km/h)^2 |
| Train mass | {{ train_mass_t }} t |
| Available sighting distance | {{ sighting_distance_m }} m |
| Required sighting time | {{ required_sighting_time_s }} s |
| Overlap distance | {{ overlap_distance_m }} m |
| Warning time | {{ warning_time_s }} s |
| Minimum warning time | {{ minimum_warning_time_s }} s |

Checks:

- Speed in m/s equals train speed divided by 3.6.
- Davis resistance equals `A + B x speed_kmh + C x speed_kmh^2`; resistance force equals that value times train mass divided by 1000.
- Effective braking deceleration equals braking rate minus `9.81 x grade_percent / 100`.
- Braking distance equals `speed_m_s^2 / (2 x effective_deceleration) + speed_m_s x reaction_time_s`.
- Sighting time equals sighting distance divided by speed.
- Warning strike-in distance equals speed times warning time.
- Overall pass score is `1.0` only when sighting, warning-time, and overlap margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, signalling-software validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "speed_m_s": <numeric_value>,
  "davis_resistance_n_per_t": <numeric_value>,
  "resistance_force_kn": <numeric_value>,
  "effective_braking_deceleration_m_s2": <numeric_value>,
  "braking_distance_m": <numeric_value>,
  "sighting_time_s": <numeric_value>,
  "sighting_margin_s": <numeric_value>,
  "warning_strike_in_distance_m": <numeric_value>,
  "warning_margin_s": <numeric_value>,
  "overlap_margin_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
