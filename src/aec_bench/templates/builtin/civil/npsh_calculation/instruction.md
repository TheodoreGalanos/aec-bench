You are a senior civil engineer specializing in water infrastructure and pump station design.

## Problem

Calculate the Net Positive Suction Head Available (NPSHa) for a pump station suction system. Determine the pressure head, NPSHa, NPSH margin, and margin ratio to assess whether the pump will operate without cavitation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Atmospheric pressure (P_atm) | {{ atmospheric_pressure_kpa }} | kPa |
{%- if vapour_pressure_kpa is defined %}
| Vapour pressure (P_vap) | {{ vapour_pressure_kpa }} | kPa |
{%- endif %}
{%- if specific_gravity is defined %}
| Specific gravity (SG) | {{ specific_gravity }} | - |
{%- endif %}
| Static suction head (h_s) | {{ static_suction_head_m }} | m |
| Friction losses (h_f) | {{ friction_loss_m }} | m |
| NPSH required (NPSHr) | {{ npsh_required_m }} | m |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A NPSH calculation tool is available at `/workspace/npsh-calculation_calc.py`. Run it with:

```bash
python3 /workspace/npsh-calculation_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Net pressure head contribution (P_atm - P_vap) / (rho x g) in metres
2. NPSHa -- Net Positive Suction Head Available (m)
3. NPSH margin: NPSHa - NPSHr (m)
4. NPSH margin ratio: NPSHa / NPSHr (dimensionless)

## Applicable Standards

- Hydraulics Institute -- pump NPSH definitions and methodology
- ANSI/HI 9.6.1 -- NPSH margin guideline (recommends margin ratio > 1.35)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following formulas:
  - Fluid density: rho = 998 x SG (kg/m^3)
  - Pressure head: h_p = (P_atm - P_vap) x 1000 / (rho x g) where pressures are in kPa, converted to Pa by multiplying by 1000
  - NPSHa = h_p + h_s - h_f
  - NPSH margin = NPSHa - NPSHr
  - Margin ratio = NPSHa / NPSHr
- Physical constants: g = 9.81 m/s^2, rho_water = 998 kg/m^3
- Static suction head h_s is positive when the pump is below the liquid surface (flooded suction) and negative when the pump is above the liquid surface (suction lift)
- If vapour pressure or specific gravity is not provided, estimate from the site description, fluid type, and temperature

## Output Format

Show your step-by-step working in Markdown, including the density calculation, pressure head calculation, NPSHa calculation, and margin assessment. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "pressure_head_m": <numeric_value>,
  "npsh_available_m": <numeric_value>,
  "npsh_margin_m": <numeric_value>,
  "npsh_margin_ratio": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
