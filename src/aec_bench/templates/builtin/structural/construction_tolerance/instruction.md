You are a senior structural engineer specializing in construction tolerances and fit-up allowances.

## Problem

Calculate the construction tolerance allowance for a slotted connection and determine the required slot length.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Fabrication tolerance | {{ fabrication_tolerance_mm }} | mm |
| Erection tolerance | {{ erection_tolerance_mm }} | mm |
| Survey tolerance | {{ survey_tolerance_mm }} | mm |
| Movement allowance | {{ movement_allowance_mm }} | mm |
| Clearance allowance | {{ clearance_mm }} | mm |
| Component length | {{ component_length_mm }} | mm |

{% if archetype_description is defined %}
### Structural Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A construction tolerance calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Total allowance as fabrication tolerance plus erection tolerance plus survey tolerance plus movement allowance plus clearance allowance
2. RSS tolerance as the square root of the sum of squares of fabrication, erection, survey, and movement components only
3. Required slot length as component length plus twice the total allowance
4. Clearance allowance included in the total allowance

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use only the provided tolerance components.
- Do not include clearance in the RSS tolerance.
- Use the total allowance on both ends of the slot when calculating required slot length.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "total_allowance_mm": <numeric_value>,
  "rss_tolerance_mm": <numeric_value>,
  "required_slot_length_mm": <numeric_value>,
  "clearance_included_mm": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
