You are a senior civil engineer specializing in railway track engineering and continuously welded rail (CWR) design.

## Problem

Determine the thermal stress, thermal force, and stress state (compression or tension) in a continuously welded rail due to temperature change from the neutral (stress-free) temperature.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Rail cross-sectional area (A) | {{ rail_area_mm2 }} | mm² |
| Temperature change from neutral (ΔT) | {{ temperature_change_c }} | °C |
{% if thermal_expansion_coeff_micro_per_c is defined %}
| Coefficient of thermal expansion (α) | {{ thermal_expansion_coeff_micro_per_c }} | ×10⁻⁶ per °C |
{% endif %}
{% if elastic_modulus_mpa is defined %}
| Modulus of elasticity (E) | {{ elastic_modulus_mpa }} | MPa |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A thermal stress calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Thermal stress magnitude σ (MPa)
2. Thermal force magnitude F (kN)
3. Stress state: 1.0 if compression (rail hotter than neutral), -1.0 if tension (rail cooler than neutral), 0.0 if neutral

## Applicable Standards

- AREMA Manual for Railway Engineering, Chapter 5 (Track)
- UIC Code 720 R (Laying and Maintenance of CWR Track)
- ARTC Engineering Track Standard ETS-05-00

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the standard thermal stress formula for restrained rail:
  - σ = E × α × |ΔT|
  - where E is the modulus of elasticity (MPa), α is the coefficient of thermal expansion (per °C), ΔT is the temperature change from neutral (°C)
  - Report σ as a positive magnitude regardless of sign
- Calculate thermal force:
  - F = σ × A / 1000
  - where A is the rail cross-sectional area (mm²), F is in kN
  - Report F as a positive magnitude
- Determine stress state from the sign of ΔT:
  - If ΔT > 0 (rail hotter than neutral): compression → report 1.0
  - If ΔT < 0 (rail cooler than neutral): tension → report -1.0
  - If ΔT = 0: neutral → report 0.0
{% if elastic_modulus_mpa is not defined %}
- For standard rail steel: E ≈ 207,000 MPa (typical for carbon-manganese rail steel)
{% endif %}
{% if thermal_expansion_coeff_micro_per_c is not defined %}
- For standard rail steel: α ≈ 11.5 × 10⁻⁶ per °C
{% endif %}

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "thermal_stress_mpa": <numeric_value>,
  "thermal_force_kn": <numeric_value>,
  "stress_state": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
