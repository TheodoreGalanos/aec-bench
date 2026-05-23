You are a senior civil engineer specializing in driveway and access design for residential and commercial developments.

## Problem

Calculate the gradient of a driveway section and verify compliance with maximum allowable slopes per AS/NZS 2890.1:2004 and typical Australian council Development Control Plans (DCPs).

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Start level | {{ start_level_m }} | m AHD |
| End level | {{ end_level_m }} | m AHD |
| Horizontal length | {{ horizontal_length_m }} | m |
{%- if location_type is defined %}
| Location type | {{ location_type }} | - |
{%- endif %}
{%- if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A driveway gradient calculation tool is available at `/workspace/driveway-gradient-check_calc.py`. Run it with:

```bash
python3 /workspace/driveway-gradient-check_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Driveway gradient (%)
2. Maximum allowable gradient for the location type (%)
3. Compliance (1.0 if gradient is within the allowable limit, 0.0 if it exceeds it)

## Applicable Standards

- AS/NZS 2890.1:2004 — Parking facilities: Off-street car parking
- Local Council DCPs — Development Control Plans for driveway gradients

## Maximum Allowable Gradients (AS/NZS 2890.1 & Typical Council DCPs)

| Location Type | Maximum Gradient (%) | Ratio |
|---------------|---------------------|-------|
| Transition zone (first 6m from street) | 12.5 | 1:8 |
| Internal residential driveway | 25.0 | 1:4 |
| Internal commercial driveway | 20.0 | 1:5 |
| Near garage / parking area | 16.67 | 1:6 |
| Pedestrian shared access | 12.5 | 1:8 |

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following formula:
  - **Gradient (%):** G = |end_level - start_level| / horizontal_length x 100
  - Levels are in metres AHD; horizontal length is in metres
- Compliance: 1.0 if the calculated gradient is less than or equal to the maximum allowable gradient for the given location type, otherwise 0.0

## Output Format

Show your step-by-step working in Markdown, including the level difference, gradient calculation, identification of the maximum allowable gradient, and compliance assessment. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "gradient_pct": <numeric_value>,
  "max_allowable_gradient_pct": <numeric_value>,
  "compliance": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
