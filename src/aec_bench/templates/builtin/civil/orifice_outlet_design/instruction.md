You are a senior civil engineer specializing in stormwater management and detention basin design.

## Problem

Size an orifice outlet to achieve a target release rate from a detention basin using the orifice flow equation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design discharge (Q) | {{ design_flow_m3_s }} | m³/s |
{% if head_above_centreline_m is defined %}
| Head above orifice centreline (H) | {{ head_above_centreline_m }} | m |
{% endif %}
{% if discharge_coefficient is defined %}
| Discharge coefficient (Cd) | {{ discharge_coefficient }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An orifice sizing calculation tool is available at `/workspace/orifice-outlet-design_calc.py`. Run it with:

```bash
python3 /workspace/orifice-outlet-design_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Required orifice area A (m²)
2. Orifice diameter D (mm)
3. Discharge velocity through the orifice v (m/s)

## Applicable Standards

- Standard hydraulics textbook orifice flow equations

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the orifice flow equation:
  - **Q = Cd × A × √(2gH)**
  - Rearranged for area: **A = Q / (Cd × √(2gH))**
  - Diameter from area: **D = √(4A / π)**
  - Discharge velocity: **v = √(2gH)**
- Use g = 9.81 m/s²
- If no discharge coefficient is given, use Cd = 0.61 (sharp-edged circular orifice)
- The orifice is assumed to be circular and fully submerged

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "required_orifice_area_m2": <numeric_value>,
  "orifice_diameter_mm": <numeric_value>,
  "discharge_velocity_m_s": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
