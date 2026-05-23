You are a senior civil engineer specializing in roof drainage and stormwater plumbing design.

## Problem

Size downpipes for a roof catchment using the AS/NZS 3500.3 standard capacity table for round uPVC downpipes.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Roof catchment area (A) | {{ roof_catchment_area_m2 }} | m² |
{% if rainfall_intensity_mm_hr is defined %}
| Design rainfall intensity (I) | {{ rainfall_intensity_mm_hr }} | mm/hr |
{% endif %}
| Number of downpipes | {{ num_downpipes }} | - |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A downpipe sizing calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Design flow per downpipe Q (L/s)
2. Selected standard downpipe diameter (mm)
3. Full-bore capacity of the selected downpipe (L/s)
4. Compliance assessment (1.0 = pass, 0.0 = fail)

## Applicable Standards

- AS/NZS 3500.3:2025 Plumbing and Drainage — Stormwater Drainage

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following design flow formula (SI units):
  - **Design flow per downpipe:** Q = (I × A / N) / 3600
  - where I is rainfall intensity (mm/hr), A is catchment area (m²), N is number of downpipes
  - Q is in litres per second (L/s)
- Select the smallest standard uPVC round downpipe diameter from AS/NZS 3500.3 Table 4.3 whose full-bore capacity meets or exceeds the design flow:

| Diameter (mm) | Capacity (L/s) |
|---------------|----------------|
| 65 | 0.7 |
| 80 | 1.3 |
| 90 | 2.0 |
| 100 | 3.0 |
| 125 | 5.5 |
| 150 | 9.0 |

- Compliance: pass (1.0) if selected capacity >= design flow, fail (0.0) otherwise

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "design_flow_l_s": <numeric_value>,
  "selected_diameter_mm": <numeric_value>,
  "selected_capacity_l_s": <numeric_value>,
  "compliance": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
