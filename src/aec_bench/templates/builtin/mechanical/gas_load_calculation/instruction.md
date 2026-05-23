You are a senior mechanical engineer specializing in building gas services.

## Problem

Calculate connected and diversified gas load from explicit appliance loads and quantities.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Appliance 1 gas load | {{ appliance_1_load_mj_h }} | MJ/h |
| Appliance 1 quantity | {{ appliance_1_quantity }} | - |
| Appliance 2 gas load | {{ appliance_2_load_mj_h }} | MJ/h |
| Appliance 2 quantity | {{ appliance_2_quantity }} | - |
| Appliance 3 gas load | {{ appliance_3_load_mj_h }} | MJ/h |
| Appliance 3 quantity | {{ appliance_3_quantity }} | - |
| Diversity factor | {{ diversity_factor }} | - |

{% if archetype_description is defined %}
### Gas Services Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A gas load calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Connected gas load in MJ/h
2. Diversified gas load in MJ/h
3. Connected gas load in kW
4. Diversified gas load in kW

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use connected load = sum of each appliance load multiplied by its quantity.
- Use diversified load = connected load x diversity factor.
- Use 1 kW = 3.6 MJ/h.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "connected_load_mj_h": <numeric_value>,
  "diversified_load_mj_h": <numeric_value>,
  "connected_load_kw": <numeric_value>,
  "diversified_load_kw": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

