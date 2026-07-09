You are a senior naval architect specializing in classification society rule compliance.

## Problem

Calculate the IACS Rule length L for a ship under the Harmonised Common Structural Rules (CSR-H).

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Extreme length on the waterline at T_SC | {{ extreme_length_on_waterline_at_TSC_m }} | m |
{% if has_rudder_stock is defined %}
| Has rudder stock | {{ has_rudder_stock }} | - |
{% endif %}
{% if stem_to_rudder_stock_distance_m is defined %}
| Distance from stem to rudder stock centre, on the waterline at T_SC | {{ stem_to_rudder_stock_distance_m }} | m |
{% endif %}
{% if archetype_description is defined %}

### Vessel Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A Rule length calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Rule length L (m)

## Applicable Standards

- IACS Harmonised Common Structural Rules (CSR-H), edition 01 JUL 2025, Pt 1 Ch 1 Sec 4 §3.1.1

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Quote from Pt 1 Ch 1 Sec 4 §3.1.1: "The Rule length L is the distance, in m, measured on the waterline at the scantling draught T_SC from the forward side of the stem to the centre of the rudder stock. L is to be not less than 96% and need not exceed 97% of the extreme length on the waterline at the scantling draught T_SC. In ships without rudder stock (e.g. ships fitted with azimuth thrusters), the Rule length L is to be taken equal to 97% of the extreme length on the waterline at the scantling draught T_SC. In ships with unusual stem or stern arrangements, the Rule length is considered on a case-by-case basis."
- If the ship has a rudder stock, clamp the measured stem-to-rudder-stock distance to the range [0.96 x extreme length, 0.97 x extreme length].
- If the ship has no rudder stock (e.g. azimuth thrusters), L = 0.97 x extreme length on the waterline at T_SC.
- Ships with unusual stem or stern arrangements are out of scope for this calculation — assume conventional arrangements unless stated otherwise.

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answer in exactly this format:

```json
{
  "rule_length_L_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
