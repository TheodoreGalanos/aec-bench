You are a senior coastal engineer specializing in breakwater and revetment design.

## Problem

Calculate the required median armor stone weight and nominal diameter for a rubble-mound breakwater using Hudson's equation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design wave height (H) | {{ design_wave_height_m }} | m |
{% if rock_density_kg_m3 is defined %}
| Rock density (ρ_r) | {{ rock_density_kg_m3 }} | kg/m³ |
{% endif %}
{% if water_density_kg_m3 is defined %}
| Water density (ρ_w) | {{ water_density_kg_m3 }} | kg/m³ |
{% endif %}
| Slope angle (α) | {{ slope_angle_deg }} | degrees |
{% if stability_coefficient_kd is defined %}
| Stability coefficient (KD) | {{ stability_coefficient_kd }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An armor sizing calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Specific gravity of the armor rock Sr = ρ_r / ρ_w
2. Median armor unit weight W in tonnes
3. Nominal armor diameter Dn50 in metres

## Applicable Standards

- USACE Coastal Engineering Manual (CEM)
- CIRIA C683 Rock Manual

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use Hudson's equation:
  - W = (ρ_r × H³) / (KD × (Sr − 1)³ × cot(α))
  - where W is in kg, ρ_r is in kg/m³, H is in metres
  - Sr = ρ_r / ρ_w (specific gravity of rock)
  - cot(α) = cos(α) / sin(α) where α is the slope angle from horizontal
- Convert weight to tonnes: W (tonnes) = W (kg) / 1000
- Nominal diameter: Dn50 = (W / ρ_r)^(1/3) where W is in kg and ρ_r is in kg/m³

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "specific_gravity_sr": <numeric_value>,
  "armor_weight_tonnes": <numeric_value>,
  "nominal_diameter_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
