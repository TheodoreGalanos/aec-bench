You are a senior electrical engineer sizing power factor correction for a load.

## Problem

Calculate the capacitor kVAr required to improve the load power factor from the initial value to the target value.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Real power | {{ real_power_kw }} | kW |
{% if initial_power_factor is defined %}
| Initial power factor | {{ initial_power_factor }} | - |
{% endif %}
| Target power factor | {{ target_power_factor }} | - |
{% if archetype_description is defined %}

### Site Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A power factor correction sizing tool is available at `/workspace/pfc-sizing_calc.py`. Run it with:

```bash
python3 /workspace/pfc-sizing_calc.py --help
```
{% endif %}

## Required

Calculate:

1. Initial apparent power in kVA
2. Corrected apparent power in kVA
3. Required capacitor reactive power in kVAr
4. Current reduction percentage at unchanged voltage

## Constraints

- Use `phi = acos(power_factor)`.
- Use `Qc = P x (tan(phi_initial) - tan(phi_target))`.
- Use `S = P / power_factor`.
- Use apparent-power reduction as the current reduction percentage.

## Output Format

Show your working in Markdown. At the end, include a JSON block with exactly these keys:

```json
{
  "initial_apparent_power_kva": <numeric_value>,
  "corrected_apparent_power_kva": <numeric_value>,
  "required_reactive_power_kvar": <numeric_value>,
  "current_reduction_pct": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
