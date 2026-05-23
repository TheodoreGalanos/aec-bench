# ABOUTME: Prompt template for reduced lift shaft dimension tasks.
# ABOUTME: Presents car dimensions, clearances, counterweight allowance, speed, and count.

You are a senior vertical transportation engineer sizing a reduced lift shaft envelope.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Car internal width | {{ car_internal_width_mm }} | mm |
| Car internal depth | {{ car_internal_depth_mm }} | mm |
| Side clearance | {{ side_clearance_mm }} | mm |
| Front clearance | {{ front_clearance_mm }} | mm |
| Rear clearance | {{ rear_clearance_mm }} | mm |
| Counterweight width allowance | {{ counterweight_width_mm }} | mm |
| Rated speed | {{ rated_speed_m_s }} | m/s |
| Number of cars in shaft group | {{ car_count }} | count |
| Inter-car clearance | {{ inter_car_clearance_mm }} | mm |

## Constraints

- Shaft width equals car count times `(car width + 2 * side clearance + counterweight width)` plus inter-car clearances between cars.
- Shaft depth equals car depth plus front and rear clearances.
- Reduced pit depth equals `1200 + rated speed * 250`.
- Reduced headroom equals `3600 + rated speed * 500`.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "shaft_width_mm": <numeric_value>,
  "shaft_depth_mm": <numeric_value>,
  "pit_depth_mm": <numeric_value>,
  "headroom_mm": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
