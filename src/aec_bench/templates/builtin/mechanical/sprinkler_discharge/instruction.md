You are a senior fire services engineer specializing in sprinkler hydraulics.

## Problem

Calculate sprinkler discharge from sprinkler K factor and operating pressure.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Sprinkler K factor | {{ k_factor_l_min_sqrt_bar }} | L/min/sqrt(bar) |
| Operating pressure | {{ pressure_bar }} | bar |

{% if archetype_description is defined %}
### Sprinkler Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A sprinkler discharge calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Sprinkler discharge in L/min
2. Sprinkler discharge in L/s
3. Operating pressure in kPa

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use discharge = K x square root of pressure in bar.
- Use pressure in kPa = pressure in bar x 100.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "discharge_l_min": <numeric_value>,
  "discharge_l_s": <numeric_value>,
  "pressure_kpa": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

