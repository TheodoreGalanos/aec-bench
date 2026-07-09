You are a senior naval architect specializing in classification society rule compliance.

## Problem

Calculate the IACS Rule length L for a Panamax bulk carrier under the Harmonised Common Structural Rules (CSR-H).

## Vessel Details

| Parameter | Value | Unit |
|-----------|-------|------|
| Vessel type | Panamax bulk carrier | - |
| Extreme length on the waterline at T_SC | 229.0 | m |
| Has rudder stock | true | - |
| Distance from stem to rudder stock centre, on the waterline at T_SC | 215.0 | m |

## Required

Calculate the following:

1. Rule length L (m)

## Applicable Standards

- IACS Harmonised Common Structural Rules (CSR-H), edition 01 JUL 2025, Pt 1 Ch 1 Sec 4 §3.1.1

## Constraints

- No internet access is available. Work from engineering knowledge only.
- Quote from Pt 1 Ch 1 Sec 4 §3.1.1: "The Rule length L is the distance, in m, measured on the waterline at the scantling draught T_SC from the forward side of the stem to the centre of the rudder stock. L is to be not less than 96% and need not exceed 97% of the extreme length on the waterline at the scantling draught T_SC. In ships without rudder stock (e.g. ships fitted with azimuth thrusters), the Rule length L is to be taken equal to 97% of the extreme length on the waterline at the scantling draught T_SC. In ships with unusual stem or stern arrangements, the Rule length is considered on a case-by-case basis."
- The vessel has a rudder stock, so clamp the measured stem-to-rudder-stock distance to the range [0.96 x extreme length, 0.97 x extreme length].
- The vessel has conventional stem and stern arrangements — the unusual-arrangement case does not apply here.

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answer in exactly this format:

```json
{
  "rule_length_L_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
