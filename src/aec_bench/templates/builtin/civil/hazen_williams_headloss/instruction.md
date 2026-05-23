You are a senior civil engineer specializing in water infrastructure and pipe hydraulics.

## Problem

Calculate the friction head loss in a pressurised pipe using the Hazen-Williams equation. Determine the hydraulic gradient and mean flow velocity.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Flow rate (Q) | {{ flow_rate_l_s }} | L/s |
| Pipe diameter (D) | {{ pipe_diameter_mm }} | mm |
| Pipe length (L) | {{ pipe_length_m }} | m |
{% if c_factor is defined %}
| Hazen-Williams C-factor | {{ c_factor }} | — |
{% endif %}
{% if archetype_description is defined %}

### Pipe Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A head loss calculation tool is available at `/workspace/hazen-williams-headloss_calc.py`. Run it with:

```bash
python3 /workspace/hazen-williams-headloss_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Friction head loss hf (m)
2. Hydraulic gradient S (dimensionless)
3. Mean flow velocity V (m/s)

## Applicable Standards

- AWWA — American Water Works Association pipe flow references
- AS/NZS 3500 — Australian/New Zealand plumbing and drainage standard

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following formulas:
  - Convert flow rate: Q (m³/s) = Q (L/s) / 1000
  - Convert diameter: D (m) = D (mm) / 1000
  - Hazen-Williams head loss (SI): hf = 10.67 × L × Q¹·⁸⁵² / (C¹·⁸⁵² × D⁴·⁸⁷)
    where Q is in m³/s, D is in metres, L is in metres
  - Hydraulic gradient: S = hf / L
  - Flow velocity: V = Q / (π × D² / 4) where Q and D are in SI units
- If the Hazen-Williams C-factor is not given, you must infer an appropriate value from the pipe material description.

## Output Format

Show your step-by-step working in Markdown, including the unit conversions, head loss calculation, hydraulic gradient, and velocity. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "head_loss_m": <numeric_value>,
  "hydraulic_gradient": <numeric_value>,
  "flow_velocity_m_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
