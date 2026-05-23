You are a senior civil engineer specializing in hydrology and stormwater management.

## Problem

Calculate the runoff depth from a design storm event using the SCS/NRCS curve number method.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Rainfall depth (P) | {{ rainfall_depth_mm }} | mm |
{% if curve_number is defined %}
| Curve number (CN) | {{ curve_number }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A runoff calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Potential maximum retention S (mm)
2. Initial abstraction Ia (mm)
3. Runoff depth Q (mm)

## Applicable Standards

- NRCS TR-55: Urban Hydrology for Small Watersheds

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the SCS/NRCS curve number method equations (metric, all lengths in mm):
  - S = (25400 / CN) - 254
  - Ia = 0.2 * S
  - Q = (P - Ia)^2 / (P - Ia + S) when P > Ia, otherwise Q = 0
- CN ranges from ~30 (permeable sandy soil, good cover) to 98 (impervious surfaces)
- All values are in millimetres

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "potential_max_retention_mm": <numeric_value>,
  "initial_abstraction_mm": <numeric_value>,
  "runoff_depth_mm": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
