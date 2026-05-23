You are a senior civil engineer specializing in water infrastructure and pipe hydraulics.

## Problem

Verify that the flow velocity in a pipe meets the minimum and maximum velocity limits per AS/NZS 3500.1 for the given service type. Calculate the flow velocity and determine whether it complies with the applicable limits.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Pipe diameter (D) | {{ pipe_diameter_mm }} | mm |
| Flow rate (Q) | {{ flow_rate_l_s }} | L/s |
{%- if service_type is defined %}
| Service type | {{ service_type }} | - |
{%- endif %}
{%- if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A pipe velocity calculation tool is available at `/workspace/pipe-velocity-check_calc.py`. Run it with:

```bash
python3 /workspace/pipe-velocity-check_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Flow velocity V (m/s)
2. Velocity compliance (1.0 if within limits, 0.0 if outside limits)

## Applicable Standards

- AS/NZS 3500.1 Clause 3.4 — velocity limits by service type

## Velocity Limits (AS/NZS 3500.1)

| Service Type | Min Velocity (m/s) | Max Velocity (m/s) |
|---|---|---|
| Water supply | 0.6 | 3.0 |
| Sewer (gravity) | 0.6 | 4.0 |
| Stormwater | 0.6 | 6.0 |
| Fire services | 0.5 | 4.0 |

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following formulas:
  - Cross-sectional area: A = pi * (D/2)^2 where D is the diameter in metres (convert from mm)
  - Flow velocity: V = Q / A where Q is in m^3/s (convert from L/s by dividing by 1000)
  - Compliance: compare V against the min and max velocity for the given service type
- Compliance is 1.0 if min_velocity <= V <= max_velocity, otherwise 0.0

## Output Format

Show your step-by-step working in Markdown, including the unit conversions, area calculation, velocity calculation, and compliance check. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "velocity_m_s": <numeric_value>,
  "compliance": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
