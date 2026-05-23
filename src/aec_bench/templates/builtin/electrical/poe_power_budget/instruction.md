You are a senior electrical and communications engineer checking a PoE switch power budget.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Powered devices | {{ device_count }} | count |
| Power draw per device | {{ power_draw_per_device_w }} | W |
| Switch PoE budget | {{ switch_poe_budget_w }} | W |
{% if required_headroom_pct is defined %}
| Required headroom | {{ required_headroom_pct }} | % |
{% endif %}

## Constraints

- Total PoE demand equals device count times per-device draw.
- Utilization equals total demand divided by switch PoE budget.
- Available headroom equals switch budget minus total demand.
- Required headroom equals total demand times the headroom percentage.
- Headroom margin equals available headroom minus required headroom.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "total_power_requirement_w": <numeric_value>,
  "utilization_pct": <numeric_value>,
  "available_headroom_w": <numeric_value>,
  "required_headroom_w": <numeric_value>,
  "headroom_margin_w": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
