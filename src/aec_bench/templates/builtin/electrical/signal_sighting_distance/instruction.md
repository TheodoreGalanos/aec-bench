You are a senior rail signalling engineer calculating required signal sighting distance.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Maximum line speed | {{ maximum_line_speed_kmh }} | km/h |
| Service braking rate | {{ service_braking_rate_m_s2 }} | m/s2 |
| Driver reaction time | {{ driver_reaction_time_s }} | s |
{% if track_gradient_pct is defined %}
| Track gradient | {{ track_gradient_pct }} | % |
{% endif %}

## Constraints

- Convert line speed from km/h to m/s.
- Reaction distance equals speed times reaction time.
- Adjust braking rate using `a_adjusted = a + 9.81 x grade_decimal`.
- Positive grade is upgrade and negative grade is downgrade.
- Braking distance equals `v^2 / (2 a_adjusted)`.
- Required sighting distance equals reaction distance plus braking distance.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "line_speed_m_s": <numeric_value>,
  "reaction_distance_m": <numeric_value>,
  "grade_adjusted_braking_rate_m_s2": <numeric_value>,
  "braking_distance_m": <numeric_value>,
  "required_sighting_distance_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
