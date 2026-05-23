You are a senior structural engineer specializing in marine mooring checks.

## Problem

Calculate the design tension in a mooring line and check it against the line minimum breaking load.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Line tension | {{ line_tension_kn }} | kN |
| Dynamic factor | {{ dynamic_factor }} | - |
| Consequence factor | {{ consequence_factor }} | - |
| Minimum breaking load | {{ mbl_kn }} | kN |

{% if archetype_description is defined %}
### Structural Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A mooring line capacity calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Design tension as line tension multiplied by dynamic factor and consequence factor
2. Capacity margin ratio as minimum breaking load divided by design tension
3. Reserve capacity as minimum breaking load minus design tension
4. Utilisation ratio as design tension divided by minimum breaking load
5. Pass flag, where 1 means design tension does not exceed minimum breaking load and 0 means it exceeds it

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use only the explicit factors provided in the prompt.
- Do not infer extra reduction factors, safety factors, or load combinations.
- Treat the pass flag as numeric: 1 for pass, 0 for fail.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "design_tension_kn": <numeric_value>,
  "capacity_margin_ratio": <numeric_value>,
  "reserve_capacity_kn": <numeric_value>,
  "utilisation_ratio": <numeric_value>,
  "passes_capacity_check": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
