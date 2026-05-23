You are a senior civil engineer specializing in roof drainage and stormwater plumbing design.

## Problem

Size an eaves gutter for a roof catchment using the AS/NZS 3500.3 standard gutter capacity table.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Roof catchment area (A) | {{ roof_catchment_area_m2 }} | m² |
{% if rainfall_intensity_mm_hr is defined %}
| Design rainfall intensity (I) | {{ rainfall_intensity_mm_hr }} | mm/hr |
{% endif %}
| Nominated gutter profile | {{ gutter_profile }} | - |
| Gutter grade | {{ gutter_grade_pct }} | % |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A gutter sizing calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Design stormwater flow Q (L/s)
2. Capacity of the smallest adequate standard gutter at the installed grade (L/s)
3. Required (smallest adequate) standard gutter size (mm)
4. Compliance assessment (1.0 = pass, 0.0 = fail)

## Applicable Standards

- AS/NZS 3500.3:2025 Plumbing and Drainage — Stormwater Drainage

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following design flow formula (SI units):
  - **Design flow:** Q = I × A / 3600
  - where I is rainfall intensity (mm/hr), A is catchment area (m²)
  - Q is in litres per second (L/s)
- Gutter capacities at the reference grade of 1:500 (0.2%) per AS/NZS 3500.3 Table 4.2:

| Gutter Profile | Nominal Size (mm) | Capacity at 1:500 (L/s) |
|----------------|-------------------|--------------------------|
| 100mm quad | 100 | 0.6 |
| 115mm quad | 115 | 0.9 |
| 125mm half-round | 125 | 1.0 |
| 150mm quad | 150 | 1.8 |
| 150mm half-round | 150 | 2.0 |
| 175mm OG | 175 | 2.5 |

- For grades other than 1:500, capacity scales by √(grade / 0.002), where grade is expressed as a fraction (e.g. 0.2% = 0.002)
- Select the smallest standard gutter whose adjusted capacity meets or exceeds the design flow
- Compliance: pass (1.0) if selected capacity >= design flow, fail (0.0) otherwise

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "design_flow_l_s": <numeric_value>,
  "gutter_capacity_l_s": <numeric_value>,
  "required_gutter_size_mm": <numeric_value>,
  "compliance": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
