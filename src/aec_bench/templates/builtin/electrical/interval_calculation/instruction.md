You are a senior vertical transportation engineer calculating lift service interval.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Round-trip time | {{ round_trip_time_s }} | s |
{% if lift_count is defined %}
| Number of lifts | {{ lift_count }} | count |
{% endif %}

## Constraints

- Average interval equals round-trip time divided by number of lifts.
- Arrivals per five minutes equals 300 seconds divided by interval.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "interval_s": <numeric_value>,
  "arrivals_per_5min": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
