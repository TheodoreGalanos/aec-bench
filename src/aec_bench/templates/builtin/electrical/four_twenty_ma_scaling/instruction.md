You are a senior instrumentation engineer checking a 4-20 mA signal scaling calculation.

## Problem

Calculate the span percentage, current signal, and reconstructed process variable.

## Given

| Parameter | Value |
|-----------|-------|
| Process value | {{ process_value }} |
| Lower range value | {{ lower_range_value }} |
{% if upper_range_value is defined %}
| Upper range value | {{ upper_range_value }} |
{% endif %}

{% if tool_available %}
## Available Tool

A 4-20 mA scaling tool is available at `/workspace/4-20ma-scaling_calc.py`.
{% endif %}

## Constraints

- Use `span_pct = (process_value - LRV) / (URV - LRV) x 100`.
- Use `current_mA = 4 + 16 x span_fraction`.
- Reconstruct the process value from the current using the inverse relation.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "span_pct": <numeric_value>,
  "current_signal_ma": <numeric_value>,
  "reconstructed_process_value": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
