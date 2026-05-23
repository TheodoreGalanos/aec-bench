You are a senior structural engineer specializing in reduced load-combination checks.

## Problem

Calculate factored design moments and shears for three explicit load combinations, then identify the governing combination by moment.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Dead load moment | {{ dead_moment_knm }} | kNm |
| Live load moment | {{ live_moment_knm }} | kNm |
| Wind load moment | {{ wind_moment_knm }} | kNm |
| Seismic load moment | {{ seismic_moment_knm }} | kNm |
| Dead load shear | {{ dead_shear_kn }} | kN |
| Live load shear | {{ live_shear_kn }} | kN |
| Wind load shear | {{ wind_shear_kn }} | kN |
| Seismic load shear | {{ seismic_shear_kn }} | kN |
| Combination 1 dead factor | {{ combo_1_dead_factor }} | - |
| Combination 1 live factor | {{ combo_1_live_factor }} | - |
| Combination 2 dead factor | {{ combo_2_dead_factor }} | - |
| Combination 2 wind factor | {{ combo_2_wind_factor }} | - |
| Combination 3 dead factor | {{ combo_3_dead_factor }} | - |
| Combination 3 seismic factor | {{ combo_3_seismic_factor }} | - |

{% if archetype_description is defined %}
### Structural Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A load combination calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Factored moment for combination 1: dead plus live
2. Factored moment for combination 2: dead plus wind
3. Factored moment for combination 3: dead plus seismic
4. Governing moment
5. Shear associated with the governing moment combination
6. Governing combination index, where 1, 2, and 3 correspond to the combinations above

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use only the explicit factors provided in the prompt.
- Do not infer code-specific factors or additional combinations.
- Select the governing combination by maximum factored moment.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "combo_1_moment_knm": <numeric_value>,
  "combo_2_moment_knm": <numeric_value>,
  "combo_3_moment_knm": <numeric_value>,
  "governing_moment_knm": <numeric_value>,
  "governing_shear_kn": <numeric_value>,
  "governing_combination_index": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

