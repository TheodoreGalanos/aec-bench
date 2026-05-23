You are a senior civil/dams engineer specializing in seepage analysis and dam safety.

## Problem

Calculate the exit gradient at the downstream toe of a hydraulic structure and determine the factor of safety against piping failure.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Head difference (delta_h) | {{ head_difference_m }} | m |
| Seepage path length (L) | {{ seepage_path_length_m }} | m |
{% if specific_gravity is defined %}
| Specific gravity of soil solids (G_s) | {{ specific_gravity }} | - |
{% endif %}
{% if void_ratio is defined %}
| Void ratio (e) | {{ void_ratio }} | - |
{% endif %}
{% if foundation_soil_type is defined %}
| Foundation soil type | {{ foundation_soil_type }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An exit gradient calculation tool is available at `/workspace/exit-gradient_calc.py`. Run it with:

```bash
python3 /workspace/exit-gradient_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Exit gradient at the downstream toe i_exit (dimensionless)
2. Critical hydraulic gradient for piping initiation i_cr (dimensionless)
3. Factor of safety against piping FoS (dimensionless)
4. Saturated unit weight of foundation soil gamma_sat (kN/m3)
5. Buoyant unit weight of foundation soil gamma_b (kN/m3)

## Applicable Standards

- USACE EM 1110-2-1901 — Seepage Analysis and Control for Dams
- FEMA P-1032 — Dam Safety: Evaluation of Seepage

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the direct gradient approach for exit gradient:
  - **i_exit = delta_h / L_seepage**
  - Where delta_h is the head difference across the structure and L_seepage is the total seepage path length
- Use the critical gradient formula for piping initiation:
  - **i_cr = (G_s - 1) / (1 + e)**
  - Where G_s is the specific gravity of soil solids and e is the void ratio
- Factor of safety against piping:
  - **FoS = i_cr / i_exit**
  - USACE requires FoS >= 3 to 5 for dams; FoS >= 1.5 for temporary works
- Saturated unit weight:
  - **gamma_sat = (G_s + e) / (1 + e) * gamma_w**
- Buoyant (submerged) unit weight:
  - **gamma_b = gamma_sat - gamma_w = (G_s - 1) / (1 + e) * gamma_w**
- Use gamma_w = 9.81 kN/m3
- Typical specific gravity values: clean sand 2.65, silty sand 2.66, sandy silt 2.67, clayey silt 2.70, silty clay 2.72
- Typical void ratio ranges: clean sand 0.55-0.75, silty sand 0.45-0.65, sandy silt 0.40-0.60, clayey silt 0.35-0.55, silty clay 0.30-0.50

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "exit_gradient": <numeric_value>,
  "critical_gradient": <numeric_value>,
  "factor_of_safety": <numeric_value>,
  "saturated_unit_weight_kn_m3": <numeric_value>,
  "buoyant_unit_weight_kn_m3": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
