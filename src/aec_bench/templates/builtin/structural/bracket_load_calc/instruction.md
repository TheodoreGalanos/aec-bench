You are a senior structural engineer specializing in bracket connection load checks.

## Problem

Calculate reduced service and factored bracket load resultants from explicit load effects and factors.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Dead load | {{ dead_load_kn }} | kN |
| Live load | {{ live_load_kn }} | kN |
| Wind load | {{ wind_load_kn }} | kN |
| Dead load factor | {{ dead_load_factor }} | - |
| Live load factor | {{ live_load_factor }} | - |
| Wind load factor | {{ wind_load_factor }} | - |

{% if archetype_description is defined %}
### Bracket Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A bracket load calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Service vertical load
2. Factored vertical load
3. Factored lateral load
4. Factored resultant load

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use only the explicit load factors provided.
- Use resultant load = square root of factored vertical squared plus factored lateral squared.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "service_vertical_load_kn": <numeric_value>,
  "factored_vertical_load_kn": <numeric_value>,
  "factored_lateral_load_kn": <numeric_value>,
  "factored_resultant_load_kn": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

