You are a traffic-safety engineer checking a task-owned synthetic SSC-01 intersection timing, grade, and sight-distance package.

Use only the task-owned synthetic source pack values below for numeric grading. MUTCD and AASHTO-style timing and sight-distance workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-01-LH-02`
- Intersection plan: `INT-SSC01-002`
- Vertical profile: `PROF-SSC01-002`
- Signal timing sheet: `SIG-SSC01-002`
- Pedestrian crossing case: `PED-SSC01-002`
- Safety memo: `MEMO-SSC01-002`
- Approach: `NB-APPROACH-02`

## Source Values

| Item | Value |
| --- | --- |
| Approach speed | {{ approach_speed_kmh }} km/h |
| Approach grade | {{ approach_grade_pct }} % |
| Reaction time | {{ reaction_time_s }} s |
| Braking friction coefficient | {{ braking_friction_coefficient }} |
| Available sight distance | {{ available_sight_distance_m }} m |
| Yellow reaction time | {{ yellow_reaction_time_s }} s |
| Yellow deceleration | {{ yellow_deceleration_m_s2 }} m/s2 |
| Intersection width | {{ intersection_width_m }} m |
| Design vehicle length | {{ design_vehicle_length_m }} m |
| All-red speed | {{ all_red_speed_kmh }} km/h |
| Pedestrian startup time | {{ pedestrian_startup_time_s }} s |
| Crossing width | {{ crossing_width_m }} m |
| Pedestrian walk speed | {{ pedestrian_walk_speed_m_s }} m/s |
| Available pedestrian clearance | {{ pedestrian_clearance_available_s }} s |

## Required Calculations

- Convert speeds from km/h to m/s.
- Use grade as a signed decimal in the stopping-distance and yellow-interval checks.
- Braking distance is `v^2 / (2 x g x (friction + grade))`.
- Stopping distance is reaction distance plus braking distance.
- Sight-distance margin is available sight distance minus stopping distance.
- Yellow interval is `reaction + v / (2 x deceleration + 2 x g x grade)`.
- All-red interval is `(intersection width + vehicle length) / all-red speed`.
- Pedestrian clearance required is startup time plus crossing width divided by walk speed.
- Overall pass score is `1.0` only when sight distance and pedestrian clearance margins are non-negative.

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state that the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "stopping_distance_m": <numeric_value>,
  "sight_distance_margin_m": <numeric_value>,
  "yellow_interval_s": <numeric_value>,
  "all_red_interval_s": <numeric_value>,
  "ped_clearance_required_s": <numeric_value>,
  "ped_clearance_margin_s": <numeric_value>,
  "grade_adjusted_braking_distance_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
