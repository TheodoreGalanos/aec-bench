You are a senior structural materials engineer specializing in concrete mix calculations.

## Problem

Calculate cement and supplementary cementitious material quantities for a binder replacement percentage.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Total binder content | {{ total_binder_kg_m3 }} | kg/m3 |
| SCM replacement | {{ scm_replacement_pct }} | % |
| Water content | {{ water_content_kg_m3 }} | kg/m3 |

{% if archetype_description is defined %}
### Concrete Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An SCM substitution calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Cement content
2. SCM content
3. Cement reduction
4. Water-binder ratio

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use SCM content = total binder x replacement percentage / 100.
- Use cement content = total binder - SCM content.
- Use water-binder ratio = water content / total binder.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "cement_content_kg_m3": <numeric_value>,
  "scm_content_kg_m3": <numeric_value>,
  "cement_reduction_kg_m3": <numeric_value>,
  "water_binder_ratio": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

