You are a senior civil engineer specializing in hydraulic design and open channel flow.

## Problem

Calculate the flow capacity and velocity in an open channel using Manning's equation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Bottom width (b) | {{ bottom_width_m }} | m |
| Flow depth (y) | {{ flow_depth_m }} | m |
| Side slope (z H:V) | {{ side_slope_z }} | - |
{% if mannings_n is defined %}
| Manning's roughness (n) | {{ mannings_n }} | - |
{% endif %}
| Channel slope (S) | {{ channel_slope_m_per_m }} | m/m |
{% if archetype_description is defined %}

### Channel Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An open channel flow calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Flow cross-sectional area A (m²)
2. Wetted perimeter P (m)
3. Hydraulic radius R (m)
4. Flow velocity V (m/s)
5. Flow capacity Q (m³/s)
6. Froude number Fr (dimensionless)

## Applicable Standards

- HEC-22: Urban Drainage Design Manual
- ARR: Australian Rainfall and Runoff

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use Manning's equation (SI units):
  - **Velocity:** V = (1/n) × R^(2/3) × S^(1/2)
  - **Flow capacity:** Q = V × A
- For trapezoidal channel geometry (side slope z, horizontal:vertical):
  - Flow area: A = (b + z × y) × y
  - Wetted perimeter: P = b + 2 × y × √(1 + z²)
  - Hydraulic radius: R = A / P
  - Top width: T = b + 2 × z × y
- For rectangular channel (z = 0): A = b × y, P = b + 2y, R = A / P, T = b
- Froude number: Fr = V / √(g × D_h) where D_h = A / T and g = 9.81 m/s²

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "flow_area_m2": <numeric_value>,
  "wetted_perimeter_m": <numeric_value>,
  "hydraulic_radius_m": <numeric_value>,
  "flow_velocity_m_s": <numeric_value>,
  "flow_capacity_m3_s": <numeric_value>,
  "froude_number": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
