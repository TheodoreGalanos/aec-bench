You are a senior civil engineer specializing in water and wastewater infrastructure design.

## Problem

Verify that a gravity sewer pipe has adequate slope for self-cleansing velocity. Calculate the full-pipe flow velocity and capacity using Manning's equation, then determine compliance with WSAA WSA 02 velocity limits.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Pipe diameter (D) | {{ pipe_diameter_mm }} | mm |
| Pipe slope | {{ pipe_slope_pct }} | % |
{%- if mannings_n is defined %}
| Manning's roughness (n) | {{ mannings_n }} | - |
{%- endif %}
{%- if archetype_description is defined %}

### Pipe Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A sewer slope calculation tool is available at `/workspace/sewer-slope-check_calc.py`. Run it with:

```bash
python3 /workspace/sewer-slope-check_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Full-pipe flow velocity V (m/s)
2. Full-pipe flow capacity Q (L/s)
3. Self-cleansing compliance (1.0 if adequate, 0.0 if non-compliant)

## Applicable Standards

- WSAA WSA 02 — Gravity Sewerage Code of Australia
- BS EN 752 — Drain and sewer systems outside buildings

## Velocity Limits (WSAA WSA 02)

| Criterion | Velocity (m/s) |
|-----------|---------------|
| Minimum self-cleansing | 0.6 |
| Maximum (scour limit) | 4.0 |

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use Manning's equation for a full circular pipe (SI units):
  - **Hydraulic radius (full pipe):** R_h = D / 4, where D is the diameter in metres (convert from mm)
  - **Slope conversion:** S = pipe_slope_pct / 100 (convert from % to m/m)
  - **Velocity:** V = (1/n) × R_h^(2/3) × S^(1/2)
  - **Cross-sectional area:** A = π × (D/2)²
  - **Flow capacity:** Q = V × A (m³/s), then convert to L/s by multiplying by 1000
- Compliance: 1.0 if 0.6 m/s ≤ V ≤ 4.0 m/s, otherwise 0.0

## Output Format

Show your step-by-step working in Markdown, including unit conversions, hydraulic radius, velocity, capacity, and compliance check. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "full_pipe_velocity_m_s": <numeric_value>,
  "full_pipe_capacity_l_s": <numeric_value>,
  "compliance": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
