You are a senior civil engineer specializing in hydraulic design and stormwater drainage.

## Problem

Calculate the flow capacity and velocity in a circular pipe using Manning's equation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Pipe diameter (D) | {{ pipe_diameter_m }} | m |
{% if mannings_n is defined %}
| Manning's roughness (n) | {{ mannings_n }} | - |
{% endif %}
| Pipe slope (S) | {{ slope_m_per_m }} | m/m |
{% if flow_depth_ratio is defined %}
| Flow depth ratio (d/D) | {{ flow_depth_ratio }} | - |
{% endif %}
{% if archetype_description is defined %}

### Pipe Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A pipe flow calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Flow cross-sectional area A (m²)
2. Hydraulic radius R (m)
3. Flow velocity V (m/s)
4. Flow capacity Q (m³/s)

## Applicable Standards

- HEC-22: Urban Drainage Design Manual
- QUDM: Queensland Urban Drainage Manual
- PUB Code of Practice on Surface Water Drainage

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use Manning's equation (SI units):
  - **Velocity:** V = (1/n) × R^(2/3) × S^(1/2)
  - **Flow capacity:** Q = V × A
- For circular pipe geometry using the central angle method:
  - Central angle: θ = 2 × arccos(1 − 2 × d/D)
  - Flow area: A = (D² / 8) × (θ − sin(θ))
  - Wetted perimeter: P = (D / 2) × θ
  - Hydraulic radius: R = A / P
- For full pipe (d/D = 1.0): A = π×D²/4, P = π×D, R = D/4

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "flow_area_m2": <numeric_value>,
  "hydraulic_radius_m": <numeric_value>,
  "flow_velocity_m_s": <numeric_value>,
  "flow_capacity_m3_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
