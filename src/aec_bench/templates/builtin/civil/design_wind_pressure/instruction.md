You are a senior structural/wind engineer specializing in wind loading analysis for building design.

## Problem

Calculate the design wind pressure on a building surface and the total wind force on the tributary area, in accordance with AS/NZS 1170.2.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design wind speed (V_des,theta) | {{ design_wind_speed_m_per_s }} | m/s |
| Aerodynamic shape factor (C_fig) | {{ cfig }} | — |
{% if cdyn is defined %}
| Dynamic response factor (C_dyn) | {{ cdyn }} | — |
{% endif %}
{% if air_density_kg_per_m3 is defined %}
| Air density (rho_air) | {{ air_density_kg_per_m3 }} | kg/m3 |
{% endif %}
| Tributary area (A) | {{ tributary_area_m2 }} | m2 |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A wind pressure calculation tool is available at `/workspace/design-wind-pressure_calc.py`. Run it with:

```bash
python3 /workspace/design-wind-pressure_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Basic dynamic wind pressure q (kPa)
2. Design wind pressure p (kPa)
3. Total wind force on the tributary area F (kN)

## Applicable Standards

- AS/NZS 1170.2 — Structural design actions, Part 2: Wind actions (Section 2.4)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the AS/NZS 1170.2 Section 2.4 design wind pressure formula:
  - **q = 0.5 * rho_air * V_des^2** (basic dynamic pressure)
  - **p = q * C_fig * C_dyn** (design wind pressure on the surface)
  - **F = p * A** (total wind force on the tributary area)
- A positive C_fig indicates pressure towards the surface; a negative C_fig indicates suction away from the surface.
- If air density is not given, use the standard value rho_air = 1.2 kg/m3.
- If C_dyn is not given, use C_dyn = 1.0 (appropriate for most low-rise and medium-rise structures that are not dynamically sensitive).
- For tall or slender structures, C_dyn may exceed 1.0 and should be calculated per AS/NZS 1170.2 Section 6.
- Convert Pa to kPa (divide by 1000) and N to kN (divide by 1000) for final answers.

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "dynamic_pressure_kpa": <numeric_value>,
  "design_pressure_kpa": <numeric_value>,
  "total_force_kn": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
