You are a senior civil engineer specializing in hydrology and stormwater drainage.

## Problem

Calculate the peak stormwater runoff from a catchment using the rational method.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
{% if runoff_coefficient is defined %}
| Runoff coefficient (C) | {{ runoff_coefficient }} | - |
{% endif %}
| Rainfall intensity (I) | {{ rainfall_intensity_mm_hr }} | mm/hr |
| Catchment area (A) | {{ catchment_area_ha }} | ha |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A peak runoff calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Peak runoff Q in cubic metres per second (m³/s)
2. Peak runoff Q in litres per second (L/s)

## Applicable Standards

- Australian Rainfall and Runoff (ARR)
- HEC-22 Urban Drainage Design Manual

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the rational method equation (SI units):
  - Q = C × I × A / 360
  - where Q is in m³/s, I is in mm/hr, A is in hectares
  - The divisor 360 is the unit conversion factor
- Convert to litres per second: Q (L/s) = Q (m³/s) × 1000
- The rational method is valid for catchments up to approximately 80 hectares

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "peak_runoff_m3_s": <numeric_value>,
  "peak_runoff_l_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
