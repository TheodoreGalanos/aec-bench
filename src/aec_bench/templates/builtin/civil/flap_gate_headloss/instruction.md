You are a senior civil engineer specializing in stormwater drainage and outfall hydraulics.

## Problem

Calculate the energy loss through a flap gate (non-return valve) installed on a stormwater outfall. Determine the discharge coefficient, headloss, unseating head, and effective capacity reduction.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Pipe diameter | {{ pipe_diameter_mm }} | mm |
| Flow velocity (V) | {{ flow_velocity_m_per_s }} | m/s |
{% if gate_type is defined %}
| Gate type | {{ gate_type }} | - |
{% endif %}
| Upstream head | {{ upstream_head_m }} | m |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A flap gate headloss calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Discharge coefficient Cd for the gate type
2. Energy loss through the flap gate (m)
3. Minimum unseating head to open the gate (m)
4. Effective capacity reduction compared to an open pipe (%)

## Applicable Standards

- Manufacturer data (Waterman, Hydro Gate, Mosbaek)
- Hydraulic references for flap gate discharge coefficients

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the orifice-based headloss equation:

  **Headloss:** h_loss = V² / (2 × g × Cd²)

  where:
  - V = mean flow velocity in the pipe (m/s)
  - g = 9.81 m/s²
  - Cd = discharge coefficient (depends on gate type)

- Discharge coefficient ranges by gate type:
  - Side-hinged: Cd = 0.60 – 0.65 (use midpoint 0.625)
  - Top-hinged: Cd = 0.55 – 0.60 (use midpoint 0.575)
  - Duckbill (elastomeric): Cd = 0.50 – 0.55 (use midpoint 0.525)

- Unseating head lookup by pipe diameter:

  | Diameter (mm) | Unseating head (m) |
  |---------------|--------------------|
  | 150 | 0.010 |
  | 225 | 0.012 |
  | 300 | 0.015 |
  | 375 | 0.020 |
  | 450 | 0.025 |
  | 600 | 0.030 |
  | 750 | 0.035 |
  | 900 | 0.040 |
  | 1200 | 0.050 |

- **Capacity reduction:** capacity_reduction_percent = (1 − Cd) × 100

## Output Format

Show your step-by-step working in Markdown, including the discharge coefficient selection, headloss calculation, unseating head lookup, and capacity reduction determination. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "headloss_m": <numeric_value>,
  "unseating_head_m": <numeric_value>,
  "capacity_reduction_percent": <numeric_value>,
  "discharge_coefficient": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
