You are a senior electrical engineer specializing in building services.

## Problem

Calculate the voltage drop for a three-phase cable circuit using the impedance
method, and determine whether it complies with the maximum allowable voltage
drop limit.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Circuit type | Three-phase | - |
| Load current | 45 | A |
| Cable length (one way) | 80 | m |
| Cable resistance (R) | 0.524 | ohm/km |
| Cable reactance (X) | 0.08 | ohm/km |
| Power factor (cos phi) | 0.85 | - |
| System voltage (line-to-line) | 400 | V |
| Maximum allowable voltage drop | 5 | % |

## Required

Calculate the following:
- Voltage drop (V)
- Voltage drop as a percentage of system voltage (%)
- Compliance with the 5% limit (1 if compliant, 0 if not)

## Applicable Standards

- AS/NZS 3008.1 — Electrical installations: selection of cables (for reference)
- AS/NZS 3000 — Wiring rules (for reference)

Exact clause citation is optional.

## Constraints

- No internet access is available. Work from engineering knowledge only.
- Use the impedance method (not simplified resistance-only method).

## Output Format

Show your step-by-step working in Markdown, including the formulas you use and
intermediate calculations. At the end of your solution, include a JSON block
with your final answers in exactly this format:

```json
{
  "voltage_drop_v": <numeric_value>,
  "voltage_drop_pct": <numeric_value>,
  "compliance": <1_or_0>
}
```

Write your complete solution to `/workspace/output.md`.
