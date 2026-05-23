You are a senior mechanical engineer specializing in pump operating range checks.

## Problem

Check whether a pump operating flow is inside explicit preferred and allowable operating ranges.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Operating flow | {{ operating_flow_l_s }} | L/s |
| Best efficiency point flow | {{ best_efficiency_flow_l_s }} | L/s |
| POR minimum ratio | {{ por_min_ratio }} | - |
| POR maximum ratio | {{ por_max_ratio }} | - |
| AOR minimum ratio | {{ aor_min_ratio }} | - |
| AOR maximum ratio | {{ aor_max_ratio }} | - |

{% if archetype_description is defined %}
### Pump Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A POR/AOR compliance tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Operating flow ratio relative to best efficiency point
2. Lower and upper margins against the preferred operating range
3. Numeric preferred operating range flag
4. Numeric allowable operating range flag

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use only the explicit POR and AOR ratios provided.
- Use flow ratio = operating flow / best efficiency point flow.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "flow_ratio": <numeric_value>,
  "por_margin_low": <numeric_value>,
  "por_margin_high": <numeric_value>,
  "within_por": <numeric_value>,
  "within_aor": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

