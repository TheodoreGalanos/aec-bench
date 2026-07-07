You are a senior naval architect specializing in classification society rule compliance.

## Problem

Calculate the IACS Block coefficient C_B for a Capesize bulk carrier under the Harmonised Common Structural Rules (CSR-H).

## Vessel Details

| Parameter | Value | Unit |
|-----------|-------|------|
| Vessel type | Capesize bulk carrier | - |
| Moulded displacement at T_SC (Delta) | 180000.0 | t |
| Rule length (L) | 280.0 | m |
| Moulded breadth (B) | 45.0 | m |
| Scantling draught (T_SC) | 18.0 | m |

## Required

Calculate the following:

1. Block coefficient C_B (dimensionless)

## Applicable Standards

- IACS Harmonised Common Structural Rules (CSR-H), edition 01 JUL 2025, Pt 1 Ch 1 Sec 4 §3.1.8

## Constraints

- No internet access is available. Work from engineering knowledge only.
- Quote from Pt 1 Ch 1 Sec 4 §3.1.8: "C_B, the block coefficient at the draught, T_SC is defined in the following equation: C_B = Delta / (1.025 x L x B x T_SC)" where Delta is the moulded displacement of the ship at draught T_SC (in tonnes), L is the Rule length (m), B is the moulded breadth (m), and T_SC is the scantling draught (m).
- Use a seawater density of 1.025 t/m^3, per the formula above.

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answer in exactly this format:

```json
{
  "block_coefficient_CB": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
