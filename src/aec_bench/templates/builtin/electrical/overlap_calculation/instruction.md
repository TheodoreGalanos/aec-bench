# ABOUTME: Prompt template for rail signal overlap calculation tasks.
# ABOUTME: Presents speed, braking, gradient, reaction, adhesion, and clearance data.

You are a senior rail signalling engineer checking overlap distance.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Maximum approach speed | {{ maximum_approach_speed_kmh }} | km/h |
| Emergency braking rate | {{ emergency_braking_rate_m_s2 }} | m/s2 |
| Track gradient | {{ track_gradient_pct }} | % |
| Reaction time | {{ reaction_time_s }} | s |
| Danger point distance beyond signal | {{ danger_point_distance_m }} | m |
| Low adhesion factor | {{ low_adhesion_factor }} | - |

## Constraints

- Convert speed from km/h to m/s using division by 3.6.
- Gradient-adjusted braking rate equals emergency braking rate times low adhesion factor plus `9.81 * gradient / 100`.
- Reaction distance equals speed times reaction time.
- Timed overlap option equals `speed^2 / (2 * gradient-adjusted braking rate)`.
- Full-speed overlap equals reaction distance plus timed overlap option.
- Danger point clearance equals danger point distance minus full-speed overlap.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "approach_speed_m_s": <numeric_value>,
  "gradient_adjusted_braking_rate_m_s2": <numeric_value>,
  "reaction_distance_m": <numeric_value>,
  "full_speed_overlap_m": <numeric_value>,
  "timed_overlap_option_m": <numeric_value>,
  "danger_point_clearance_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
