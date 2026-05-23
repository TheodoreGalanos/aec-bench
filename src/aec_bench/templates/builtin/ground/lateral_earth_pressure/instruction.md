You are a senior geotechnical engineer specializing in retaining wall design.

## Problem

Calculate the active and passive lateral earth pressure coefficients and forces acting on a retaining wall using {{ theory | capitalize }} theory.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Wall height (H) | {{ wall_height_m }} | m |
{% if friction_angle_deg is defined %}
| Effective friction angle (φ') | {{ friction_angle_deg }} | degrees |
{% endif %}
{% if cohesion_kpa is defined %}
| Effective cohesion (c') | {{ cohesion_kpa }} | kPa |
{% endif %}
{% if unit_weight_kn_m3 is defined %}
| Soil unit weight (γ) | {{ unit_weight_kn_m3 }} | kN/m³ |
{% endif %}
{% if backfill_slope_deg is defined %}
| Backfill slope angle (β) | {{ backfill_slope_deg }} | degrees |
{% endif %}
{% if wall_friction_angle_deg is defined %}
| Wall friction angle (δ) | {{ wall_friction_angle_deg }} | degrees |
{% endif %}
{% if surcharge_kpa is defined %}
| Uniform surcharge (q) | {{ surcharge_kpa }} | kPa |
{% endif %}
| Theory | {{ theory }} | - |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A lateral earth pressure calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Active earth pressure coefficient Ka
2. Passive earth pressure coefficient Kp
3. Active pressure at the base of the wall σ_a (kPa)
4. Passive pressure at the base of the wall σ_p (kPa)
5. Total active force per unit wall length Pa (kN/m)
6. Total passive force per unit wall length Pp (kN/m)
7. Point of application of the active force above the base (m)

## Applicable Standards

- Rankine, W.J.M. (1857) — On the Stability of Loose Earth
- Coulomb, C.A. (1776) — Essai sur une application des règles de maximis et minimis

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the specified theory ({{ theory }}) for calculating earth pressure coefficients.
- **Rankine theory** (horizontal backfill):
  - Ka = tan²(45° − φ'/2)
  - Kp = tan²(45° + φ'/2)
- **Rankine theory** (inclined backfill with slope β):
  - Ka = cosβ × (cosβ − √(cos²β − cos²φ')) / (cosβ + √(cos²β − cos²φ'))
  - Kp = cosβ × (cosβ + √(cos²β − cos²φ')) / (cosβ − √(cos²β − cos²φ'))
- **Coulomb theory** (vertical wall, wall friction δ, backfill slope β):
  - Ka = cos²φ' / [cosδ × (1 + √(sin(φ'+δ)×sin(φ'−β) / (cosδ × cosβ)))²]
  - Kp = cos²φ' / [cosδ × (1 − √(sin(φ'−δ)×sin(φ'+β) / (cosδ × cosβ)))²]
- **Active pressure at depth z:** σ_a = Ka × γ × z + Ka × q − 2c'√Ka
- **Passive pressure at depth z:** σ_p = Kp × γ × z + Kp × q + 2c'√Kp
- **Total active force:** Pa = 0.5 × Ka × γ × H² + Ka × q × H − 2c'√Ka × H
- **Total passive force:** Pp = 0.5 × Kp × γ × H² + Kp × q × H + 2c'√Kp × H
- If total active force is negative (cohesion dominates), report Pa = 0
- Point of application is computed from the moment equilibrium of the pressure components
- For φ' = 0 (purely cohesive soil): Ka = Kp = 1.0

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "ka": <numeric_value>,
  "kp": <numeric_value>,
  "active_pressure_at_base_kpa": <numeric_value>,
  "passive_pressure_at_base_kpa": <numeric_value>,
  "total_active_force_kn_m": <numeric_value>,
  "total_passive_force_kn_m": <numeric_value>,
  "active_force_application_point_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
