You are a senior naval architect specializing in classification society rule compliance.

## Problem

Calculate the IACS Freeboard length L_LL for a general cargo ship under the Harmonised Common Structural Rules (CSR-H).

## Vessel Details

| Parameter | Value | Unit |
|-----------|-------|------|
| Vessel type | General cargo ship | - |
| Total length on a waterline at 85% of the least moulded depth | 180.0 | m |
| Has rudder stock | true | - |
| Length from the fore side of the stem to the axis of the rudder stock, on that waterline | 170.0 | m |

## Required

Calculate the following:

1. Freeboard length L_LL (m)

## Applicable Standards

- IACS Harmonised Common Structural Rules (CSR-H), edition 01 JUL 2025, Pt 1 Ch 1 Sec 4 §3.1.2

## Constraints

- No internet access is available. Work from engineering knowledge only.
- Quote from Pt 1 Ch 1 Sec 4 §3.1.2: "The freeboard length L_LL, in m, is to be taken as 96% of the total length on a waterline at 85% of the least moulded depth measured from the top of the keel, or as the length from the fore side of the stem to the axis of the rudder stock on that waterline, if that be greater. For ships without a rudder stock, the length L_LL is to be taken as 96% of the waterline at 85% of the least moulded depth."
- The vessel has a rudder stock, so L_LL is the GREATER of (a) 96% of the total length on the 85%-depth waterline and (b) the measured length from the fore side of the stem to the axis of the rudder stock on that waterline.
- The vessel has a conventional stem contour — the concave-stem-contour special case does not apply here.

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answer in exactly this format:

```json
{
  "freeboard_length_LLL_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
