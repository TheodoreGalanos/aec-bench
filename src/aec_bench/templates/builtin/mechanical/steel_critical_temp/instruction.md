You are a senior mechanical fire safety engineer specializing in structural fire checks.

## Problem

Calculate the critical steel temperature from the member load ratio and determine whether the critical temperature falls below the fire protection trigger.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Load ratio mu | {{ load_ratio }} | - |
| Protection trigger temperature | {{ protection_trigger_c }} | C |

{% if archetype_description is defined %}
### Structural Fire Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A steel critical temperature calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Critical steel temperature (C)
2. Protection margin relative to the trigger temperature (C)
3. Numeric fire protection requirement indicator: 0 no, 1 yes

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use theta_cr = 39.19 x ln(1 / (0.9674 x mu^3.833) - 1) + 482.
- Use protection margin = critical temperature - protection trigger temperature.
- Set protection_required to 1 when the critical temperature is below the trigger, otherwise 0.
- Treat the load ratio as an explicit input; do not recalculate section capacity.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "critical_temperature_c": <numeric_value>,
  "protection_margin_c": <numeric_value>,
  "protection_required": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
