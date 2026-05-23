You are a senior signalling power engineer sizing an equipment supply.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Equipment power | {{ equipment_power_w }} | W each |
| Equipment quantity | {{ equipment_quantity }} | count |
| Diversity factor | {{ diversity_factor }} | - |
{% if future_expansion_pct is defined %}
| Future expansion allowance | {{ future_expansion_pct }} | % |
{% endif %}
| Supply power factor | {{ supply_power_factor }} | - |

## Constraints

- Connected load equals equipment power times quantity.
- Maximum demand equals connected load times diversity factor.
- Future allowance equals maximum demand times the expansion percentage.
- Recommended supply kVA equals demand plus allowance, divided by power factor and 1000.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "total_connected_load_w": <numeric_value>,
  "maximum_demand_w": <numeric_value>,
  "future_allowance_w": <numeric_value>,
  "recommended_supply_size_kva": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
