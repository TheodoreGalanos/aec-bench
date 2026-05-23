You are a senior fire safety engineer specializing in smoke tenability checks.

## Problem

Calculate smoke visibility from extinction coefficient and compare it with an explicit minimum visibility criterion.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Extinction coefficient | {{ extinction_coefficient_m_inv }} | 1/m |
| Visibility constant | {{ visibility_constant }} | - |
| Minimum visibility | {{ minimum_visibility_m }} | m |

{% if archetype_description is defined %}
### Tenability Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A visibility criterion calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Visibility in metres
2. Visibility margin above the minimum criterion
3. Visibility utilisation ratio
4. Numeric pass flag, where 1 means the criterion is satisfied

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use visibility = visibility constant / extinction coefficient.
- Use only the explicit minimum visibility criterion provided.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "visibility_m": <numeric_value>,
  "visibility_margin_m": <numeric_value>,
  "visibility_utilisation_ratio": <numeric_value>,
  "criterion_satisfied": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

