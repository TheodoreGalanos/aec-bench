You are a senior naval architect specializing in classification society rule compliance.

## Problem

Calculate the IACS Block coefficient C_B for a ship under the Harmonised Common Structural Rules (CSR-H).

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
{% if moulded_displacement_t is defined %}
| Moulded displacement at T_SC (Delta) | {{ moulded_displacement_t }} | t |
{% endif %}
| Rule length (L) | {{ rule_length_L_m }} | m |
| Moulded breadth (B) | {{ moulded_breadth_B_m }} | m |
| Scantling draught (T_SC) | {{ scantling_draught_TSC_m }} | m |
{% if archetype_description is defined %}

### Vessel Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A Block coefficient calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Block coefficient C_B (dimensionless)

## Applicable Standards

- IACS Harmonised Common Structural Rules (CSR-H), edition 01 JUL 2025, Pt 1 Ch 1 Sec 4 §3.1.8

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Quote from Pt 1 Ch 1 Sec 4 §3.1.8: "C_B, the block coefficient at the draught, T_SC is defined in the following equation: C_B = Delta / (1.025 x L x B x T_SC)" where Delta is the moulded displacement of the ship at draught T_SC (in tonnes), L is the Rule length (m), B is the moulded breadth (m), and T_SC is the scantling draught (m).
- Use a seawater density of 1.025 t/m^3, per the formula above.
{% if moulded_displacement_t is not defined %}
- The moulded displacement is not given directly — infer an appropriate value from the vessel description above.
{% endif %}

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answer in exactly this format:

```json
{
  "block_coefficient_CB": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
