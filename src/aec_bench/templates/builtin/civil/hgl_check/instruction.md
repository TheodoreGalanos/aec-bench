You are a senior civil engineer specializing in stormwater drainage design and hydraulic analysis.

## Problem

Perform a hydraulic grade line (HGL) check for a single stormwater pipe reach between two pits. Determine whether the HGL at the upstream pit remains below the pit surface level with adequate clearance to prevent surcharging.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design flow (Q) | {{ design_flow_m3_per_s }} | m³/s |
| Pipe diameter (DN) | {{ pipe_diameter_mm }} | mm |
| Pipe length (L) | {{ pipe_length_m }} | m |
{% if mannings_n is defined %}
| Manning's n | {{ mannings_n }} | - |
{% endif %}
{% if pit_loss_coefficient is defined %}
| Pit loss coefficient (K) | {{ pit_loss_coefficient }} | - |
{% endif %}
| Tailwater level (HGL downstream) | {{ tailwater_level_m }} | m AHD |
| Surface level at upstream pit | {{ surface_level_m }} | m AHD |
{% if minimum_clearance_mm is defined %}
| Minimum required clearance | {{ minimum_clearance_mm }} | mm |
{% endif %}
{% if archetype_description is defined %}

### Pipe and Pit Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A hydraulic grade line calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following for the pipe reach:

1. Flow velocity V in the pipe (m/s)
2. Friction head loss h_f through the pipe (m)
3. Pit/junction head loss h_pit at the upstream pit (m)
4. HGL elevation at the upstream pit (m AHD)
5. Clearance between surface level and HGL (mm)
6. Surcharge ratio (HGL / surface level)
7. Pass/fail assessment (pass if clearance >= minimum clearance)

## Applicable Standards

- ARR 2019: Australian Rainfall and Runoff
- QUDM: Queensland Urban Drainage Manual
- Local Council Development Control Plans (DCPs)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Assume the pipe is flowing full (pressure flow assumption for HGL check).
- Use Manning's equation (SI units) for friction loss:
  - **Pipe area:** A = pi x D² / 4
  - **Hydraulic radius (full pipe):** R = D / 4
  - **Flow velocity:** V = Q / A
  - **Friction slope:** S_f = (V x n / R^(2/3))²
  - **Friction loss:** h_f = S_f x L
- Use the standard minor loss equation for pit losses:
  - **Pit loss:** h_pit = K x V² / (2g), where g = 9.81 m/s²
- **HGL at upstream pit:** HGL_up = HGL_down + h_f + h_pit
- **Clearance:** clearance = (surface_level - HGL_up) x 1000 (in mm)
- **Surcharge ratio:** surcharge_ratio = HGL_up / surface_level
- **Pass/fail:** pass (1.0) if clearance >= minimum clearance, fail (0.0) otherwise
{% if minimum_clearance_mm is not defined %}
- If minimum clearance is not specified, use 150 mm as the default threshold.
{% endif %}

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "flow_velocity_m_per_s": <numeric_value>,
  "friction_loss_m": <numeric_value>,
  "pit_loss_m": <numeric_value>,
  "hgl_upstream_m": <numeric_value>,
  "clearance_mm": <numeric_value>,
  "surcharge_ratio": <numeric_value>,
  "pass_fail": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
