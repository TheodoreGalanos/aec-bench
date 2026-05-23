You are a senior traffic signals engineer calculating pedestrian clearance timing.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Crosswalk length | {{ crosswalk_length_m }} | m |
{% if walking_speed_m_s is defined %}
| Walking speed | {{ walking_speed_m_s }} | m/s |
{% endif %}

## Constraints

- Use `clearance_time = crosswalk_length / walking_speed`.
- Round the operational flashing clearance value up to the next whole second.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "pedestrian_clearance_time_s": <numeric_value>,
  "pedestrian_clearance_rounded_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
