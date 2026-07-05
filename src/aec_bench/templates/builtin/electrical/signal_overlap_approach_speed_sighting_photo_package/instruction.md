You are a signalling design reviewer checking `SSC-02-LH-06`, a task-owned synthetic SSC-02 signal overlap, approach speed, and sighting photo package.

Use only the task-owned synthetic source pack values below for numeric grading. Signal sighting and overlap workflows shape the context only; this instance does not run signalling software, parse a real photo log, or validate an operator standard.

## Scene

- Design case: `CASE-SSC02-SIGHT-06`
- Signal arrangement: `SIG-02-ARRANGE-06`
- Approach speed table: `SPEED-02-APPROACH-06`
- Sighting photo log: `PHOTO-02-SIGHT-06`
- Route grade data: `GRADE-02-ROUTE-06`
- Sighting criterion: `CRIT-02-SIGHT-06`
- Sighting review response: `MEMO-02-SIGHT-06`

## Source Values

| Item | Value |
|------|-------|
| Approach speed | {{ approach_speed_kmh }} km/h |
| Reaction time | {{ reaction_time_s }} s |
| Braking rate | {{ braking_rate_m_s2 }} m/s^2 |
| Adverse grade | {{ grade_percent }} % |
| Available sighting distance | {{ available_sighting_distance_m }} m |
| Required sighting time | {{ required_sighting_time_s }} s |
| Provided overlap | {{ provided_overlap_m }} m |
| Distance to danger point | {{ danger_point_distance_m }} m |
| Photo chainage | {{ photo_chainage_m }} m |
| Signal chainage | {{ signal_chainage_m }} m |
| Maximum photo offset | {{ max_photo_offset_m }} m |
| Warning time | {{ warning_time_s }} s |

Checks:

- Approach speed in m/s equals approach speed divided by 3.6.
- Stopping distance uses the grade-adjusted braking deceleration.
- Sighting time equals available sighting distance divided by approach speed.
- Overlap margin equals provided overlap minus distance to danger point.
- Photo offset equals the absolute difference between photo chainage and signal chainage.
- Overall pass score is `1.0` only when sighting, stopping-distance, overlap, and photo-offset margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, signal-plan validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "approach_speed_m_s": <numeric_value>,
  "effective_braking_deceleration_m_s2": <numeric_value>,
  "stopping_distance_m": <numeric_value>,
  "sighting_time_s": <numeric_value>,
  "sighting_time_margin_s": <numeric_value>,
  "stopping_distance_margin_m": <numeric_value>,
  "overlap_margin_m": <numeric_value>,
  "photo_offset_m": <numeric_value>,
  "photo_offset_margin_m": <numeric_value>,
  "warning_distance_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
