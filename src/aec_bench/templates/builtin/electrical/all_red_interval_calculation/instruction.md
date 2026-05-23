You are a senior traffic signals engineer calculating an all-red clearance interval.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Intersection width | {{ intersection_width_m }} | m |
| Vehicle length | {{ vehicle_length_m }} | m |
{% if vehicle_speed_m_s is defined %}
| Vehicle speed | {{ vehicle_speed_m_s }} | m/s |
{% endif %}

## Constraints

- Clearance distance equals intersection width plus vehicle length.
- Raw all-red interval equals clearance distance divided by vehicle speed.
- Round the operational all-red interval to one decimal place and cap it at 6.0 s.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "clearance_distance_m": <numeric_value>,
  "raw_all_red_interval_s": <numeric_value>,
  "all_red_interval_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
