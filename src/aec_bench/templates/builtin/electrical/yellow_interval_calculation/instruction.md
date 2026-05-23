You are a senior traffic signals engineer calculating a yellow change interval.

## Problem

Calculate the yellow interval duration for the signal approach using the metric ITE kinematic equation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Approach speed | {{ approach_speed_kmh }} | km/h |
| Perception-reaction time | {{ perception_reaction_time_s }} | s |
| Deceleration rate | {{ deceleration_rate_m_s2 }} | m/s2 |
{% if road_grade_pct is defined %}
| Road grade | {{ road_grade_pct }} | % |
{% endif %}
{% if archetype_description is defined %}

### Site Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A yellow interval calculation tool is available at `/workspace/yellow-interval-calculation_calc.py`. Run it with:

```bash
python3 /workspace/yellow-interval-calculation_calc.py --help
```
{% endif %}

## Required

Calculate:

1. Approach speed in m/s
2. Grade-adjusted denominator in the stopping term
3. Yellow interval in seconds
4. Yellow interval rounded to one decimal place

## Constraints

- Convert speed using `v_m_s = v_km_h / 3.6`.
- Use the metric ITE form `Y = t + v / (2a + 19.62G)`.
- `G` is grade as a decimal, positive for upgrade and negative for downgrade.
- Round the final signal timing value to one decimal place.

## Output Format

Show your working in Markdown. At the end, include a JSON block with exactly these keys:

```json
{
  "approach_speed_m_s": <numeric_value>,
  "grade_adjusted_denominator": <numeric_value>,
  "yellow_interval_s": <numeric_value>,
  "yellow_interval_rounded_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
