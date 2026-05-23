You are a senior civil/dams engineer specializing in spillway hydraulics and energy dissipation design.

## Problem

Estimate the stilling basin dimensions required for energy dissipation downstream of a spillway, using the USBR method based on the entry Froude number and the Belanger conjugate depth equation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Unit discharge (q) | {{ unit_discharge_m3_s_m }} | m³/s/m |
| Drop height (ΔH) | {{ drop_height_m }} | m |
{% if tailwater_depth_m is defined %}
| Tailwater depth (d_tw) | {{ tailwater_depth_m }} | m |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A stilling basin sizing calculation tool is available at `/workspace/stilling-basin-sizing_calc.py`. Run it with:

```bash
python3 /workspace/stilling-basin-sizing_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Froude number at basin entry Fr₁
2. Sequent (conjugate) depth d₂ (m)
3. Required stilling basin length L_basin (m)
4. USBR basin type recommendation (0 = none, 1 = Type I, 2 = Type II, 3 = Type III)

## Applicable Standards

- USBR Hydraulic Design of Stilling Basins
- USACE EM 1110-2-1603 — Hydraulic Design of Spillways

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the energy-based supercritical velocity approximation:
  - **V₁ = sqrt(2 × g × ΔH)**
- Compute supercritical depth from continuity:
  - **d₁ = q / V₁**
- Compute Froude number at basin entry:
  - **Fr₁ = V₁ / sqrt(g × d₁)**
- Compute sequent depth using the Belanger equation:
  - **d₂ = (d₁ / 2) × (sqrt(1 + 8 × Fr₁²) − 1)**
- Select basin type and compute basin length L_basin = k × d₂:
  - Fr₁ < 2.5: no basin needed (k = 0, type = 0)
  - 2.5 ≤ Fr₁ < 4.5: USBR Type I pre-formed basin (k = 4.0, type = 1)
  - 4.5 ≤ Fr₁ < 9.0: USBR Type II dentated sill basin (k = 4.5, type = 2)
  - Fr₁ ≥ 9.0: USBR Type III baffle block basin (k = 4.0, type = 3)
- Use g = 9.81 m/s²
- Report basin type as a numeric code: 0.0, 1.0, 2.0, or 3.0

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "froude_number": <numeric_value>,
  "sequent_depth_m": <numeric_value>,
  "basin_length_m": <numeric_value>,
  "basin_type": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
