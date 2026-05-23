You are a senior fire services engineer specializing in hydrant flow tests.

## Problem

Calculate available fire flow at a target residual pressure from a hydrant flow test.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Static pressure | {{ static_pressure_kpa }} | kPa |
| Residual pressure during test | {{ residual_pressure_kpa }} | kPa |
| Test flow | {{ test_flow_l_s }} | L/s |
| Target residual pressure | {{ target_residual_pressure_kpa }} | kPa |

{% if archetype_description is defined %}
### Hydrant Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An available flow calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate test pressure drop, target pressure drop, available flow in L/s, and available flow in m3/h.

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use available flow = test flow x ((static - target residual) / (static - test residual))^0.54.
- Use 1 L/s = 3.6 m3/h.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "pressure_drop_test_kpa": <numeric_value>,
  "pressure_drop_target_kpa": <numeric_value>,
  "available_flow_l_s": <numeric_value>,
  "available_flow_m3_h": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

