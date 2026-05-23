You are a senior geotechnical/dam engineer specializing in embankment slope stability and seismic assessment.

## Problem

Calculate the factor of safety of an embankment slope under pseudo-static seismic loading using the infinite slope method, and determine the yield (critical) acceleration.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Slope angle (β) | {{ slope_angle_deg }} | degrees |
| Depth to slip surface (z) | {{ slip_depth_m }} | m |
{% if cohesion_kpa is defined %}
| Effective cohesion (c') | {{ cohesion_kpa }} | kPa |
{% endif %}
{% if friction_angle_deg is defined %}
| Effective friction angle (φ') | {{ friction_angle_deg }} | degrees |
{% endif %}
{% if unit_weight_kn_m3 is defined %}
| Bulk unit weight (γ) | {{ unit_weight_kn_m3 }} | kN/m³ |
{% endif %}
| Pore pressure ratio (ru) | {{ pore_pressure_ratio }} | - |
| Horizontal seismic coefficient (kh) | {{ kh }} | - |
{% if kv is defined %}
| Vertical seismic coefficient (kv) | {{ kv }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A pseudo-static slope stability calculation tool is available at `/workspace/fos-seismic_calc.py`. Run it with:

```bash
python3 /workspace/fos-seismic_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Factor of safety under pseudo-static seismic loading (FoS)
2. Yield acceleration ky — the horizontal seismic coefficient at which FoS = 1.0
3. Yield acceleration ratio ky / kh

## Applicable Standards

- USACE EM 1110-2-1902 — Slope Stability (pseudo-static method)
- ICOLD Bulletin 148 — Selecting Seismic Parameters for Large Dams

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the pseudo-static infinite slope method with the following formulation:
  - **Driving shear stress**: T_d = γ·z·[(1 − kv)·sin(β) + kh·cos(β)]·cos(β)
  - **Normal effective stress**: σ'_n = γ·z·[(1 − kv)·cos(β) − kh·sin(β)]·cos(β)
  - **Pore pressure**: u = ru·γ·z·cos²(β)
  - **Resisting shear stress**: T_r = c' + (σ'_n − u)·tan(φ')
  - **Factor of safety**: FoS = T_r / T_d
- The vertical seismic coefficient kv acts upward (reduces effective weight), which is the conservative assumption.
- If kv is not provided, assume kv = 0.
- Yield acceleration ky is solved by setting FoS = 1.0 and solving for kh analytically.
- USACE EM 1110-2-1902 requires FoS ≥ 1.0 for the pseudo-static case; a yield ratio > 1.0 indicates ky exceeds the design kh.
- Typical horizontal seismic coefficients: 0.05–0.15 for low seismicity, 0.15–0.25 for moderate, 0.25–0.40 for high seismicity zones.

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "fos": <numeric_value>,
  "yield_acceleration_ky": <numeric_value>,
  "yield_ratio": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
