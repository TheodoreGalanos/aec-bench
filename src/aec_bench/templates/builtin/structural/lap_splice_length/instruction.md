You are a senior structural engineer specializing in reinforcement detailing.

## Problem

Calculate reduced lap splice length from a provided development length and explicit splice factors.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Development length | {{ development_length_mm }} | mm |
| Splice class factor | {{ splice_class_factor }} | - |
| Bar location factor | {{ bar_location_factor }} | - |
| Coating factor | {{ coating_factor }} | - |
| Provided lap length | {{ provided_lap_length_mm }} | mm |

{% if archetype_description is defined %}
### Detailing Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A lap splice length calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Calculated lap length
2. Required lap length rounded up to the nearest 10 mm
3. Provided lap margin
4. Numeric pass flag, where 1 means the provided lap satisfies the rounded required lap

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use only the explicit factors given in the prompt.
- Use calculated lap length = development length x splice class factor x bar location factor x coating factor.
- Round required lap length up to the nearest 10 mm.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "calculated_lap_length_mm": <numeric_value>,
  "rounded_lap_length_mm": <numeric_value>,
  "provided_margin_mm": <numeric_value>,
  "provided_lap_satisfies": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

