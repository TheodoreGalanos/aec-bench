You are a senior electrical engineer specializing in substation design and busbar short-circuit withstand analysis.

## Problem

Calculate the electromagnetic forces on rigid busbars during a three-phase short circuit using the IEEE 605 / IEC 60865-1 method. The busbars are arranged in a flat (coplanar) three-phase configuration with equal phase spacing.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Peak short-circuit current (ip) | {{ peak_short_circuit_current_ka }} | kA |
| Phase spacing (centre-to-centre) | {{ phase_spacing_mm }} | mm |
| Span length between supports | {{ span_length_m }} | m |
| Busbar width | {{ busbar_width_mm }} | mm |
| Busbar thickness | {{ busbar_thickness_mm }} | mm |
{% if support_condition is defined %}
| Support condition | {{ support_condition }} | - |
{% endif %}
{% if busbar_material is defined %}
| Busbar material | {{ busbar_material }} | - |
{% endif %}
{% if archetype_description is defined %}

### Installation Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A busbar force calculation tool is available at `/workspace/busbar-forces_calc.py`. Run it with:

```bash
python3 /workspace/busbar-forces_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Electromagnetic force per unit length on the centre phase (N/m)
2. Total peak force over one busbar span (N)
3. Maximum bending stress in the busbar (MPa)

## Applicable Standards

- IEEE 605-2008 — Guide for Bus Design in Air Insulated Substations
- IEC 60865-1:2011 — Short-circuit currents — Calculation of effects, Part 1: Definitions and calculation methods

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the IEC 60865-1 / IEEE 605 simplified method for a three-phase flat busbar arrangement:
  - **Force per unit length on centre phase:**
    Fm = (mu_0 / (2*pi)) * (sqrt(3)/2) * ip^2 / a
    where mu_0 = 4*pi*10^-7 H/m, ip is the peak short-circuit current in amperes, a is phase spacing in metres
  - **Peak force over one span:**
    F_peak = Fm * L
    where L is the span length between supports in metres
  - **Maximum bending moment:**
    M = Fm * L^2 / beta
    where beta = 8 for simply-supported, beta = 12 for fixed-both-ends
  - **Section modulus of rectangular busbar:**
    Z = w * t^2 / 6
    where w is the busbar width (mm) and t is the busbar thickness (mm), giving Z in mm^3
  - **Bending stress:**
    sigma = M / Z
    Convert units: M in N*m, Z in m^3 (or equivalently N*mm and mm^3), result in MPa
- The three-phase geometry factor sqrt(3)/2 accounts for the vector sum of forces from both adjacent phases on the centre conductor.
- All currents must be converted to amperes and all dimensions to metres for the force formula.

## Output Format

Show your step-by-step working in Markdown, including the force calculation, bending moment, section modulus, and stress derivation. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "force_per_m_n": <numeric_value>,
  "peak_force_n": <numeric_value>,
  "busbar_stress_mpa": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
