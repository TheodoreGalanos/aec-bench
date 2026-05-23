You are a senior electrical engineer specializing in substation grounding design.

## Problem

Calculate the substation grounding grid resistance and ground potential rise (GPR) using the simplified Schwarz equation from IEEE 80-2013.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
{% if soil_resistivity_ohm_m is defined %}
| Soil resistivity (ρ) | {{ soil_resistivity_ohm_m }} | Ω·m |
{% endif %}
| Grid length | {{ grid_length_m }} | m |
| Grid width | {{ grid_width_m }} | m |
| Total conductor length (L_T) | {{ total_conductor_length_m }} | m |
| Burial depth (h) | {{ burial_depth_m }} | m |
| Grid current (I_g) | {{ grid_current_ka }} | kA |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A grid resistance calculation tool is available at `/workspace/grid-resistance_calc.py`. Run it with:

```bash
python3 /workspace/grid-resistance_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Grid area A (m²) — from rectangular grid dimensions
2. Equivalent circular radius r (m) — r = √(A / π)
3. Grid resistance Rg (Ω) — using IEEE 80-2013 Equation 57
4. Ground potential rise GPR (V) — GPR = I_g × Rg

## Applicable Standards

- IEEE 80-2013 — Guide for Safety in AC Substation Grounding, Section 14.2, Equation 57

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the simplified Schwarz equation (IEEE 80-2013 Eq. 57):
  - Rg = ρ × [1/L_T + 1/√(20A) × (1 + 1/(1 + h × √(20/A)))]
  - where ρ = soil resistivity (Ω·m), L_T = total buried conductor length (m), A = grid area (m²), h = burial depth (m)
- Equivalent circular radius: r = √(A / π)
- Ground potential rise: GPR = I_g × Rg (convert grid current from kA to A)

## Output Format

Show your step-by-step working in Markdown, including intermediate values for grid area, equivalent radius, each term of the Schwarz equation, and the final grid resistance. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "grid_area_m2": <numeric_value>,
  "equivalent_radius_m": <numeric_value>,
  "grid_resistance_ohm": <numeric_value>,
  "ground_potential_rise_v": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
