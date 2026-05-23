You are a senior mechanical fire safety engineer specializing in design fire scenarios.

## Problem

Calculate heat release rate using the t-squared fire growth model and apply the peak HRR cap.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Growth coefficient alpha | {{ growth_coefficient_kw_s2 }} | kW/s^2 |
| Time from ignition t | {{ time_from_ignition_s }} | s |
| Peak HRR limit | {{ peak_hrr_kw }} | kW |

{% if archetype_description is defined %}
### Fire Scenario Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A t-squared HRR calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Unclipped t-squared HRR (kW)
2. HRR at the specified time after applying the peak limit (kW)
3. Time to reach the peak HRR (s)
4. Numeric peak-limit indicator: 0 no, 1 yes

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use HRR_unclipped = alpha x t^2.
- Use HRR_at_time = min(HRR_unclipped, peak HRR).
- Use time_to_peak = sqrt(peak HRR / alpha).
- Set peak_limited to 1 when HRR_unclipped is at or above the peak HRR, otherwise 0.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "unclipped_hrr_kw": <numeric_value>,
  "hrr_at_time_kw": <numeric_value>,
  "time_to_peak_s": <numeric_value>,
  "peak_limited": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
