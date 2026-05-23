You are a senior mechanical engineer specializing in compressed air services.

## Problem

Calculate connected and simultaneous compressed air demand from explicit tool flows, quantities, and simultaneity factor.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Tool group 1 flow | {{ tool_1_flow_l_s }} | L/s |
| Tool group 1 quantity | {{ tool_1_quantity }} | - |
| Tool group 2 flow | {{ tool_2_flow_l_s }} | L/s |
| Tool group 2 quantity | {{ tool_2_quantity }} | - |
| Tool group 3 flow | {{ tool_3_flow_l_s }} | L/s |
| Tool group 3 quantity | {{ tool_3_quantity }} | - |
| Simultaneity factor | {{ simultaneity_factor }} | - |

{% if archetype_description is defined %}
### Compressed Air Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A compressed air demand calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Connected air demand in L/s
2. Simultaneous air demand in L/s
3. Connected air demand in m3/min
4. Simultaneous air demand in m3/min

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use connected demand = sum of each tool flow multiplied by quantity.
- Use simultaneous demand = connected demand x simultaneity factor.
- Use 1 L/s = 0.06 m3/min.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "connected_demand_l_s": <numeric_value>,
  "simultaneous_demand_l_s": <numeric_value>,
  "connected_demand_m3_min": <numeric_value>,
  "simultaneous_demand_m3_min": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

