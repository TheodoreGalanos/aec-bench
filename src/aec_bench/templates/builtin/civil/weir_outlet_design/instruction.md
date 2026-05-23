You are a senior civil engineer specializing in stormwater management and detention basin design.

## Problem

Size an emergency spillway weir to safely pass the design overflow from a detention basin using the Francis weir discharge formula.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design overflow discharge (Q) | {{ design_flow_m3_s }} | m³/s |
{% if head_over_weir_m is defined %}
| Head over weir crest (H) | {{ head_over_weir_m }} | m |
{% endif %}
{% if discharge_coefficient is defined %}
| Discharge coefficient (Cd) | {{ discharge_coefficient }} | - |
{% endif %}
{% if number_of_contractions is defined %}
| Number of end contractions (n) | {{ number_of_contractions }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A weir sizing calculation tool is available at `/workspace/weir-outlet-design_calc.py`. Run it with:

```bash
python3 /workspace/weir-outlet-design_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Required weir crest length L (m)
2. Unit discharge per metre of weir crest q (m³/s/m)

## Applicable Standards

- Standard hydraulics textbook weir flow equations
- Francis formula (1883) for sharp-crested rectangular weirs

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the Francis weir discharge formula:
  - **Q = Cw × (L − 0.1 × n × H) × H^(3/2)**
  - Where the weir coefficient **Cw = Cd × √(2g)**
  - Rearranged for length: **L = Q / (Cw × H^(3/2)) + 0.1 × n × H**
  - Unit discharge: **q = Q / L**
- Use g = 9.81 m/s²
- If no discharge coefficient is given, use Cd = 0.62 (sharp-crested rectangular weir)
- If no number of contractions is given, assume n = 0 (suppressed weir)
- The weir is assumed to be a sharp-crested rectangular weir with free overflow

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "required_weir_length_m": <numeric_value>,
  "unit_discharge_m3_s_per_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
