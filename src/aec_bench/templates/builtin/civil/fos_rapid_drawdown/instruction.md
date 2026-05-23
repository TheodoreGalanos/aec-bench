You are a senior geotechnical/dams engineer specializing in embankment slope stability and dam safety assessments.

## Problem

Calculate the factor of safety for an upstream embankment slope before and after rapid reservoir drawdown using the simplified infinite slope method per USACE EM 1110-2-1902.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Upstream slope angle (beta) | {{ slope_angle_deg }} | degrees |
| Slip surface depth (z) | {{ slip_depth_m }} | m |
{% if cohesion_kpa is defined %}
| Effective cohesion (c') | {{ cohesion_kpa }} | kPa |
{% endif %}
{% if friction_angle_deg is defined %}
| Effective friction angle (phi') | {{ friction_angle_deg }} | degrees |
{% endif %}
{% if saturated_unit_weight_kn_m3 is defined %}
| Saturated unit weight (gamma_sat) | {{ saturated_unit_weight_kn_m3 }} | kN/m3 |
{% endif %}
| Initial reservoir level | {{ initial_reservoir_level_m }} | m |
| Final reservoir level | {{ final_reservoir_level_m }} | m |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A rapid drawdown factor of safety calculation tool is available at `/workspace/fos-rapid-drawdown_calc.py`. Run it with:

```bash
python3 /workspace/fos-rapid-drawdown_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Factor of safety before drawdown FoS_before (dimensionless) — submerged steady-state condition
2. Factor of safety after rapid drawdown FoS_after (dimensionless) — undrained pore pressures
3. Drawdown ratio R (dimensionless)
4. Undrained pore pressure at the slip surface u (kPa)

## Applicable Standards

- USACE EM 1110-2-1902 — Slope Stability (Chapter 13: Rapid Drawdown)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the **simplified infinite slope method** with the following approach:
- **Buoyant unit weight:**
  - **gamma_sub = gamma_sat - gamma_w**
- **Before drawdown** (slope submerged, steady state):
  - Normal stress: **sigma_n = gamma_sub * z * cos^2(beta)**
  - Shear stress: **tau = gamma_sub * z * sin(beta) * cos(beta)**
  - **FoS_before = (c' + sigma_n * tan(phi')) / tau**
- **After rapid drawdown** (external water removed, pore pressures undrained):
  - Total normal stress: **sigma_n = gamma_sat * z * cos^2(beta)**
  - Pore pressure: **u = gamma_w * z * cos^2(beta)** (unchanged from pre-drawdown)
  - Effective normal stress: **sigma_n' = gamma_sub * z * cos^2(beta)**
  - Driving shear stress: **tau = gamma_sat * z * sin(beta) * cos(beta)** (full saturated weight)
  - **FoS_after = (c' + sigma_n' * tan(phi')) / tau**
- **Drawdown ratio:**
  - **R = (initial_level - final_level) / initial_level**
- Use **gamma_w = 9.81 kN/m3**
- USACE minimum acceptable FoS for rapid drawdown is typically 1.1 to 1.3
- Typical material properties for compacted clay embankments: c' = 5-25 kPa, phi' = 18-32 degrees, gamma_sat = 17-21 kN/m3

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "fos_before_drawdown": <numeric_value>,
  "fos_after_drawdown": <numeric_value>,
  "drawdown_ratio": <numeric_value>,
  "pore_pressure_kpa": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
