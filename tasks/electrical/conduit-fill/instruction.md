You are a senior electrical engineer specializing in ICT and communications infrastructure.

## Problem

Calculate the conduit fill percentage for a mixed cable installation and
determine whether it complies with the maximum fill ratio standard.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Conduit internal diameter | 50 | mm |
| Cat6 cables | 6 | count |
| Cat6 cable outer diameter | 6.2 | mm |
| Fiber optic cables | 2 | count |
| Fiber cable outer diameter | 3.0 | mm |
| Maximum fill ratio | 40 | % |

## Required

Calculate the following:
- Total cable cross-sectional area (mm^2)
- Conduit internal cross-sectional area (mm^2)
- Fill percentage (as a number, e.g. 10.5, not 0.105)
- Compliance with the 40% fill limit (1 if compliant, 0 if not)

## Applicable Standards

- ANSI/TIA-569 — Telecommunications pathways and spaces (for reference)
- AS/NZS 3080 — Telecommunications installations (for reference)

Exact clause citation is optional.

## Constraints

- No internet access is available. Work from engineering knowledge only.
- Use the cable outer diameter (including jacket) for area calculations.

## Output Format

Show your step-by-step working in Markdown, including the formulas you use and
intermediate calculations. At the end of your solution, include a JSON block
with your final answers in exactly this format:

```json
{
  "total_cable_area_mm2": <numeric_value>,
  "conduit_area_mm2": <numeric_value>,
  "fill_pct": <numeric_value>,
  "compliance": <1_or_0>
}
```

Write your complete solution to `/workspace/output.md`.
