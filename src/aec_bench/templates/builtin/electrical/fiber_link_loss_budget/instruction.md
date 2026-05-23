You are a senior communications engineer checking an optical fibre link budget.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Fibre length | {{ fiber_length_km }} | km |
| Fibre attenuation | {{ fiber_attenuation_db_per_km }} | dB/km |
| Connector count | {{ connector_count }} | - |
| Connector loss | {{ connector_loss_db }} | dB |
| Splice count | {{ splice_count }} | - |
| Splice loss | {{ splice_loss_db }} | dB |
{% if system_loss_budget_db is defined %}
| System loss budget | {{ system_loss_budget_db }} | dB |
{% endif %}

## Constraints

- Fibre loss equals length times attenuation.
- Connector and splice losses equal count times per-item loss.
- Total link loss is the sum of fibre, connector, and splice losses.
- Power margin equals system budget minus total link loss.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "fiber_loss_db": <numeric_value>,
  "connector_loss_total_db": <numeric_value>,
  "splice_loss_total_db": <numeric_value>,
  "total_link_loss_db": <numeric_value>,
  "power_margin_db": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
