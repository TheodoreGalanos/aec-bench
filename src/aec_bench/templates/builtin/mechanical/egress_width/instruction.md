You are a senior fire and life-safety engineer specializing in egress design checks.

## Problem

Calculate required egress width from occupant load and an explicit width-per-occupant criterion.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Occupant load | {{ occupant_load }} | persons |
| Width per occupant | {{ width_per_occupant_mm }} | mm/person |
| Provided egress width | {{ provided_width_mm }} | mm |

{% if archetype_description is defined %}
### Egress Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An egress width calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Required egress width
2. Provided width margin
3. Width utilisation ratio
4. Numeric pass flag, where 1 means the provided width satisfies the requirement

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use required width = occupant load x width per occupant.
- Use only the explicit width-per-occupant criterion provided.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "required_width_mm": <numeric_value>,
  "provided_margin_mm": <numeric_value>,
  "utilisation_ratio": <numeric_value>,
  "width_satisfies": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

