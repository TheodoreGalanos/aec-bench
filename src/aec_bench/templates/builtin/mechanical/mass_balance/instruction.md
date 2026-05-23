You are a senior mechanical process engineer specializing in process balance checks.

## Problem

Check global mass balance closure from two inlet streams, two outlet streams, and an explicit closure tolerance.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Inlet stream 1 | {{ inlet_1_kg_h }} | kg/h |
| Inlet stream 2 | {{ inlet_2_kg_h }} | kg/h |
| Outlet stream 1 | {{ outlet_1_kg_h }} | kg/h |
| Outlet stream 2 | {{ outlet_2_kg_h }} | kg/h |
| Closure tolerance | {{ closure_tolerance_pct }} | % |

{% if archetype_description is defined %}
### Process Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A mass balance calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate total inlet flow, total outlet flow, imbalance, closure error percentage, and numeric pass flag.

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use imbalance = total inlet - total outlet.
- Use closure error = absolute imbalance / total inlet x 100.
- Use only the explicit closure tolerance provided.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "total_inlet_kg_h": <numeric_value>,
  "total_outlet_kg_h": <numeric_value>,
  "imbalance_kg_h": <numeric_value>,
  "closure_error_pct": <numeric_value>,
  "closure_satisfied": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

