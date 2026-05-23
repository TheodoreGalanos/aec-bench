You are a senior communications cabling engineer checking conduit fill.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Conduit internal diameter | {{ conduit_internal_diameter_mm }} | mm |
| Cable count | {{ cable_count }} | count |
| Cable outer diameter | {{ cable_outer_diameter_mm }} | mm |
{% if maximum_fill_pct is defined %}
| Maximum fill | {{ maximum_fill_pct }} | % |
{% endif %}

## Constraints

- Treat the conduit and cables as circular cross sections.
- Total cable area equals cable count times cable area.
- Fill percentage equals total cable area divided by conduit internal area.
- Fill margin equals maximum fill percentage minus actual fill percentage.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "total_cable_area_mm2": <numeric_value>,
  "conduit_area_mm2": <numeric_value>,
  "fill_percentage": <numeric_value>,
  "fill_margin_pct": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
