You are a senior rail signalling engineer calculating level crossing strike-in distance.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Maximum train speed | {{ maximum_train_speed_kmh }} | km/h |
| Minimum warning time | {{ minimum_warning_time_s }} | s |
| Road user clearance time | {{ road_user_clearance_time_s }} | s |
| Barrier lowering time | {{ barrier_lowering_time_s }} | s |
{% if system_delay_s is defined %}
| System delay | {{ system_delay_s }} | s |
{% endif %}

## Constraints

- Convert train speed from km/h to m/s.
- Total warning time equals the sum of all timing components.
- Strike-in distance equals train speed in m/s times total warning time.
- Minimum warning margin equals total warning time minus minimum warning time.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "maximum_train_speed_m_s": <numeric_value>,
  "total_warning_time_s": <numeric_value>,
  "strike_in_distance_m": <numeric_value>,
  "minimum_warning_margin_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
