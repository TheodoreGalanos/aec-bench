You are a senior dams engineer specializing in embankment dam slope stability and seepage analysis.

## Problem

Calculate the factor of safety against shallow translational slope failure on an embankment dam slope under steady-state seepage conditions using the infinite slope method.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Embankment slope angle (β) | {{ slope_angle_deg }} | degrees |
| Depth to failure plane (z) | {{ failure_depth_m }} | m |
{% if cohesion_kpa is defined %}
| Effective cohesion (c') | {{ cohesion_kpa }} | kPa |
{% endif %}
{% if friction_angle_deg is defined %}
| Effective friction angle (φ') | {{ friction_angle_deg }} | degrees |
{% endif %}
{% if saturated_unit_weight_kn_m3 is defined %}
| Saturated unit weight (γ_sat) | {{ saturated_unit_weight_kn_m3 }} | kN/m³ |
{% endif %}
| Pore pressure ratio (ru) | {{ pore_pressure_ratio }} | - |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A slope stability calculation tool is available at `/workspace/fos-steady-state_calc.py`. Run it with:

```bash
python3 /workspace/fos-steady-state_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Factor of safety against slope failure FoS (dimensionless)
2. Driving shear stress along the failure plane τ_d (kPa)
3. Resisting shear stress along the failure plane τ_r (kPa)

## Applicable Standards

- USACE EM 1110-2-1902 — Slope Stability
- ANCOLD Guidelines on Design Criteria for Concrete Gravity Dams and Embankment Dams

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the infinite slope equation with pore pressure ratio for steady-state seepage:
  - **Pore pressure:** u = ru × γ_sat × z
  - **Driving shear stress:** τ_d = γ_sat × z × sin(β) × cos(β)
  - **Normal effective stress:** σ'_n = γ_sat × z × cos²(β) - u
  - **Resisting shear stress:** τ_r = c' + σ'_n × tan(φ')
  - **Factor of safety:** FoS = τ_r / τ_d
- Use γ_w = 9.81 kN/m³ (for reference; the ru formulation does not require γ_w directly)
- USACE EM 1110-2-1902 requires minimum FoS of 1.5 for steady-state seepage conditions
- Typical embankment fill properties:
  - Compacted clay: c' = 10–30 kPa, φ' = 18–26°, γ_sat = 19–21 kN/m³
  - Sandy gravel shell: c' ≈ 0 kPa, φ' = 34–40°, γ_sat = 20–22 kN/m³
  - Homogeneous earth fill: c' = 5–20 kPa, φ' = 22–30°, γ_sat = 18–20 kN/m³

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "fos": <numeric_value>,
  "driving_stress_kpa": <numeric_value>,
  "resisting_stress_kpa": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
