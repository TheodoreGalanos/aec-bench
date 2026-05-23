You are a senior mechanical engineer specializing in pump systems.

## Problem

Apply the pump affinity laws to estimate the same pump's performance at a new rotational speed.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Original speed N1 | {{ original_speed_rpm }} | rpm |
| New speed N2 | {{ new_speed_rpm }} | rpm |
| Original flow Q1 | {{ original_flow_l_s }} | L/s |
| Original head H1 | {{ original_head_m }} | m |
| Original power P1 | {{ original_power_kw }} | kW |

{% if archetype_description is defined %}
### Operating Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A pump affinity law calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Speed ratio N2/N1
2. New flow rate Q2 (L/s)
3. New total head H2 (m)
4. New pump power P2 (kW)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Assume the same pump geometry, the same fluid, dynamically similar operation, and no cavitation limitation.
- Use Q2 = Q1 x (N2/N1).
- Use H2 = H1 x (N2/N1)^2.
- Use P2 = P1 x (N2/N1)^3.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "speed_ratio": <numeric_value>,
  "new_flow_l_s": <numeric_value>,
  "new_head_m": <numeric_value>,
  "new_power_kw": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
