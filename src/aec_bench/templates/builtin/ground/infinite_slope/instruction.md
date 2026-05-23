You are a senior geotechnical engineer specializing in slope stability.

## Problem

Calculate the factor of safety against shallow slope failure using the infinite slope method.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Slope angle (β) | {{ slope_angle_deg }} | degrees |
{% if friction_angle_deg is defined %}
| Effective friction angle (φ') | {{ friction_angle_deg }} | degrees |
{% endif %}
{% if cohesion_kpa is defined %}
| Effective cohesion (c') | {{ cohesion_kpa }} | kPa |
{% endif %}
{% if unit_weight_kn_m3 is defined %}
| Soil unit weight (γ) | {{ unit_weight_kn_m3 }} | kN/m³ |
{% endif %}
| Depth to failure surface (z) | {{ failure_depth_m }} | m |
{% if water_table_depth_m is defined %}
| Water table depth (zw) | {{ water_table_depth_m }} | m |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A slope stability calculation tool is available at `/workspace/infinite_slope_calc.py`. Run it with:

```bash
python3 /workspace/infinite_slope_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Pore water pressure at the failure surface u (kPa)
2. Driving shear stress along the failure plane (kPa)
3. Resisting shear stress along the failure plane (kPa)
4. Factor of safety FoS

## Applicable Standards

- Standard geotechnical textbook infinite slope analysis

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the infinite slope equation:
  - Driving stress: τ_d = γ·z·sin(β)·cos(β)
  - Normal effective stress: σ'_n = γ·z·cos²(β) - u
  - Resisting stress: τ_r = c' + σ'_n·tan(φ')
  - FoS = τ_r / τ_d
- Pore pressure (seepage parallel to slope): u = γ_w·(z - zw)·cos²(β) when zw < z, otherwise u = 0
- Use γ_w = 9.81 kN/m³

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "pore_pressure_kpa": <numeric_value>,
  "driving_stress_kpa": <numeric_value>,
  "resisting_stress_kpa": <numeric_value>,
  "factor_of_safety": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
