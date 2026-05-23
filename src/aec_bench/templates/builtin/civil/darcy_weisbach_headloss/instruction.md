You are a senior civil engineer specializing in water infrastructure and pipe hydraulics.

## Problem

Calculate the friction head loss in a pressurised pipe using the Darcy-Weisbach equation. Determine the Darcy friction factor using the Swamee-Jain explicit approximation (for turbulent flow) or the laminar flow formula as appropriate.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Flow rate (Q) | {{ flow_rate_m3_s }} | m³/s |
| Pipe diameter (D) | {{ pipe_diameter_m }} | m |
| Pipe length (L) | {{ pipe_length_m }} | m |
{% if roughness_height_mm is defined %}
| Roughness height (ε) | {{ roughness_height_mm }} | mm |
{% endif %}
{% if archetype_description is defined %}

### Pipe Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A head loss calculation tool is available at `/workspace/darcy-weisbach-headloss_calc.py`. Run it with:

```bash
python3 /workspace/darcy-weisbach-headloss_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Mean flow velocity V (m/s)
2. Reynolds number Re
3. Darcy friction factor f
4. Friction head loss hf (m)

## Applicable Standards

- AWWA — American Water Works Association pipe flow references
- Darcy-Weisbach equation for pressure loss in pipe flow
- Swamee-Jain (1976) explicit approximation for the Darcy friction factor

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following formulas:
  - Flow velocity: V = Q / (π × D² / 4)
  - Reynolds number: Re = V × D / ν
  - Darcy friction factor (turbulent, Re ≥ 2300): Swamee-Jain approximation
    f = 0.25 / [log₁₀(ε/(3.7×D) + 5.74/Re⁰·⁹)]²
  - Darcy friction factor (laminar, Re < 2300): f = 64 / Re
  - Head loss: hf = f × (L/D) × (V² / (2×g))
- Physical constants: g = 9.81 m/s²
- If kinematic viscosity is not provided, assume water at 20°C: ν = 1.004 × 10⁻⁶ m²/s
- Convert roughness height from mm to m before using in the Swamee-Jain equation

## Output Format

Show your step-by-step working in Markdown, including the velocity calculation, Reynolds number determination, friction factor method selection, and final head loss. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "flow_velocity_m_s": <numeric_value>,
  "reynolds_number": <numeric_value>,
  "friction_factor": <numeric_value>,
  "head_loss_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
