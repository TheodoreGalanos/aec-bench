You are a senior electrical engineer specializing in overhead transmission lines.

## Problem

Calculate the conductor sag and total conductor length for a single level span
using catenary equations. The conductor hangs between two towers at equal height.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Span length | 250 | m |
| Conductor unit weight | 7.58 | N/m |
| Horizontal tension | 64500 | N |

## Required

Calculate the following:
- Catenary constant (m)
- Maximum sag at mid-span (m)
- Total conductor length between attachment points (m)

## Applicable Standards

- IEC 60826 — Design criteria of overhead transmission lines (for reference)
- AS/NZS 7000 — Overhead line design (for reference)

Exact clause citation is optional.

## Constraints

- No internet access is available. Work from engineering knowledge only.
- Use catenary (not parabolic) equations for this calculation.

## Output Format

Show your step-by-step working in Markdown, including the formulas you use and
intermediate calculations. At the end of your solution, include a JSON block
with your final answers in exactly this format:

```json
{
  "catenary_constant_m": <numeric_value>,
  "sag_m": <numeric_value>,
  "conductor_length_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
