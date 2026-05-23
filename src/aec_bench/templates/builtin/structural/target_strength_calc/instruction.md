You are a senior structural engineer specializing in concrete mix design.

## Problem

Calculate the required target mean compressive strength for a concrete mix from the specified strength, production standard deviation, and reliability margin.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Specified compressive strength f'c | {{ specified_strength_mpa }} | MPa |
| Historical standard deviation s | {{ standard_deviation_mpa }} | MPa |
| Reliability multiplier k | {{ k_factor }} | - |
| Minimum margin | {{ minimum_margin_mpa }} | MPa |

{% if archetype_description is defined %}
### Concrete Production Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A target strength calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Statistical margin k x s (MPa)
2. Governing margin after checking the minimum margin (MPa)
3. Required average compressive strength f'cr (MPa)
4. Margin above specified strength (MPa)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use statistical margin = k x standard deviation.
- Use governing margin = max(statistical margin, minimum margin).
- Use target mean strength f'cr = f'c + governing margin.
- Treat the k-factor and minimum margin as explicit project inputs; do not infer a different code formula.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "statistical_margin_mpa": <numeric_value>,
  "governing_margin_mpa": <numeric_value>,
  "target_mean_strength_mpa": <numeric_value>,
  "margin_above_specified_mpa": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
