You are a senior mechanical engineer specializing in water and wastewater treatment.

## Problem

Calculate hydraulic retention time for a treatment unit from reactor volume and flow rate.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Reactor volume | {{ reactor_volume_m3 }} | m3 |
| Flow rate | {{ flow_rate_m3_d }} | m3/d |

{% if archetype_description is defined %}
### Treatment Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An HRT calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Hydraulic retention time in days
2. Hydraulic retention time in hours
3. Flow rate in m3/h

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use HRT days = reactor volume / flow rate.
- Use HRT hours = HRT days x 24.
- Use flow rate in m3/h = flow rate in m3/d / 24.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "hrt_days": <numeric_value>,
  "hrt_hours": <numeric_value>,
  "flow_rate_m3_h": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
