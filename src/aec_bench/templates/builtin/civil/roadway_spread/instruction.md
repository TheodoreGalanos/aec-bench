You are a senior civil engineer specializing in roadway drainage and stormwater inlet design.

## Problem

Calculate the width of water spread on a roadway gutter and the flow depth at the curb using the HEC-22 Manning's equation for a triangular gutter cross-section.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Gutter flow (Q) | {{ gutter_flow_m3_s }} | m³/s |
| Roadway cross-slope (Sx) | {{ cross_slope_pct }} | % |
| Longitudinal slope (S_L) | {{ longitudinal_slope_pct }} | % |
{% if mannings_n is defined %}
| Manning's roughness (n) | {{ mannings_n }} | - |
{% endif %}
{% if archetype_description is defined %}

### Road Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A roadway spread calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Spread width T (m) — the width of water spread from the curb face across the roadway
2. Flow depth at curb d (m) — the depth of flow at the curb face

## Applicable Standards

- HEC-22: Urban Drainage Design Manual (FHWA)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use Manning's equation for a triangular gutter cross-section (SI units):
  - **Flow equation:** Q = (K_u / n) × Sx^(5/3) × S_L^(1/2) × T^(8/3)
  - where K_u = 0.376 (SI), Sx = cross-slope (m/m), S_L = longitudinal slope (m/m), T = spread (m)
- Solve for spread width:
  - **T** = (Q × n / (K_u × Sx^(5/3) × S_L^(1/2)))^(3/8)
- Flow depth at curb:
  - **d** = T × Sx
- Convert slopes from percentage to m/m before computation (divide by 100).

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "spread_width_m": <numeric_value>,
  "curb_depth_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
