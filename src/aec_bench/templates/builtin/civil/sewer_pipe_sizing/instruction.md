You are a senior civil engineer specializing in water and sewer infrastructure design.

## Problem

Size a gravity sewer pipe to convey the design flow. Select the smallest standard pipe diameter whose full-pipe capacity equals or exceeds the design flow, then determine the resulting velocity and flow depth ratio.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design flow | {{ design_flow_l_s }} | L/s |
| Upstream invert elevation | {{ upstream_invert_m }} | m AHD |
| Downstream invert elevation | {{ downstream_invert_m }} | m AHD |
| Pipe length | {{ pipe_length_m }} | m |
{%- if mannings_n is defined %}
| Manning's roughness (n) | {{ mannings_n }} | - |
{%- endif %}
{%- if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A sewer pipe sizing tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Selected standard pipe diameter (mm) from: 150, 225, 300, 375, 450, 525, 600, 675, 750, 900, 1050, 1200
2. Pipe longitudinal slope (%)
3. Full-pipe flow velocity (m/s)
4. Approximate flow depth ratio d/D

## Applicable Standards

- WSAA WSA 02: Gravity Sewerage Code of Australia
- PUB Code of Practice on Sewerage and Sanitary Works
- AS 4130: Polyethylene (PE) Pipes for Pressure Applications

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Compute pipe slope from invert elevations:
  - **Slope:** S = |upstream_invert - downstream_invert| / pipe_length (m/m)
- For each standard diameter, compute full-pipe capacity using Manning's equation:
  - **Full-pipe area:** A = pi * D^2 / 4
  - **Hydraulic radius:** R = D / 4
  - **Full-pipe capacity:** Q_full = (1/n) * A * R^(2/3) * S^(1/2)
- Select the **smallest** standard diameter where Q_full >= design flow.
- Full-pipe velocity: V = Q_full / A
- Flow depth ratio (approximate): d/D = Q_design / Q_full

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "selected_diameter_mm": <numeric_value>,
  "pipe_slope_pct": <numeric_value>,
  "full_pipe_velocity_m_s": <numeric_value>,
  "flow_depth_ratio": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
