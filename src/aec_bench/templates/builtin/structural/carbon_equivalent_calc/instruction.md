You are a senior structural engineer specializing in steel specification and welding.

## Problem

Calculate the steel carbon equivalent using the IIW formula and determine numeric weldability risk indicators.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Carbon C | {{ carbon_pct }} | % |
| Manganese Mn | {{ manganese_pct }} | % |
| Chromium Cr | {{ chromium_pct }} | % |
| Molybdenum Mo | {{ molybdenum_pct }} | % |
| Vanadium V | {{ vanadium_pct }} | % |
| Nickel Ni | {{ nickel_pct }} | % |
| Copper Cu | {{ copper_pct }} | % |
| Caution threshold | {{ caution_threshold_pct }} | % |
| High-risk threshold | {{ high_risk_threshold_pct }} | % |

{% if archetype_description is defined %}
### Steel Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A carbon equivalent calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Carbon equivalent CE (%)
2. Margin above the caution threshold (%)
3. Margin above the high-risk threshold (%)
4. Numeric weldability risk class: 0 low, 1 caution, 2 high
5. Numeric preheat indication: 0 no, 1 yes

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use CE = C + Mn/6 + (Cr + Mo + V)/5 + (Ni + Cu)/15.
- Use risk class 0 when CE is below the caution threshold.
- Use risk class 1 when CE is at or above the caution threshold and below the high-risk threshold.
- Use risk class 2 when CE is at or above the high-risk threshold.
- Set preheat indicated to 1 when CE is at or above the caution threshold, otherwise 0.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "carbon_equivalent_pct": <numeric_value>,
  "caution_margin_pct": <numeric_value>,
  "high_risk_margin_pct": <numeric_value>,
  "weldability_risk_index": <numeric_value>,
  "preheat_indicated": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
