You are a senior geotechnical engineer specializing in foundation design.

## Problem

Calculate the ultimate and allowable bearing capacity of a shallow foundation using Terzaghi's 1943 bearing capacity equation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Footing shape | {{ footing_shape }} | - |
| Footing width (B) | {{ footing_width_m }} | m |
| Embedment depth (Df) | {{ embedment_depth_m }} | m |
{% if cohesion_kpa is defined %}
| Effective cohesion (c') | {{ cohesion_kpa }} | kPa |
{% endif %}
{% if friction_angle_deg is defined %}
| Effective friction angle (φ') | {{ friction_angle_deg }} | degrees |
{% endif %}
{% if unit_weight_kn_m3 is defined %}
| Soil unit weight (γ) | {{ unit_weight_kn_m3 }} | kN/m³ |
{% endif %}
{% if water_table_depth_m is defined %}
| Water table depth | {{ water_table_depth_m }} | m |
{% endif %}
| Factor of safety | {{ factor_of_safety }} | - |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A bearing capacity calculation tool is available at `/workspace/bearing_capacity_calc.py`. Run it with:

```bash
python3 /workspace/bearing_capacity_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Bearing capacity factor Nc
2. Bearing capacity factor Nq
3. Bearing capacity factor Nγ
4. Ultimate bearing capacity qu (kPa)
5. Allowable bearing capacity qa (kPa)

## Applicable Standards

- Terzaghi, K. (1943) — Theoretical Soil Mechanics, John Wiley & Sons

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use Terzaghi's original bearing capacity equation:
  - **Strip footing:** qu = c'·Nc + q·Nq + 0.5·γ·B·Nγ
  - **Square footing:** qu = 1.3·c'·Nc + q·Nq + 0.4·γ·B·Nγ
  - **Circular footing:** qu = 1.3·c'·Nc + q·Nq + 0.3·γ·B·Nγ
- Overburden pressure q = γ·Df
- Apply water table corrections when the water table is within the influence zone (above Df + B):
  - Use γ_w = 9.81 kN/m³
  - Adjust overburden pressure and effective unit weight based on water table position
- Allowable bearing capacity qa = qu / FoS
- For φ' = 0 (undrained clay): Nc = 5.7, Nq = 1.0, Nγ = 0.0

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "nc": <numeric_value>,
  "nq": <numeric_value>,
  "ngamma": <numeric_value>,
  "ultimate_bearing_capacity_kpa": <numeric_value>,
  "allowable_bearing_capacity_kpa": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
