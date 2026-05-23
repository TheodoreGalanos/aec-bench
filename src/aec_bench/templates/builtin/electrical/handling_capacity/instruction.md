You are a senior vertical transportation engineer calculating lift handling capacity.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Building population | {{ building_population }} | persons |
| Round-trip time | {{ round_trip_time_s }} | s |
| Car capacity | {{ car_capacity_persons }} | persons |
| Number of lifts | {{ lift_count }} | count |
{% if car_loading_factor_pct is defined %}
| Car loading factor | {{ car_loading_factor_pct }} | % |
{% endif %}

## Constraints

- Loaded car capacity equals rated car capacity times loading factor.
- Passengers per five minutes equals `300 x lift_count x loaded_capacity / RTT`.
- Handling capacity percentage equals passengers per five minutes divided by population.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "passengers_per_5min": <numeric_value>,
  "handling_capacity_pct": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
