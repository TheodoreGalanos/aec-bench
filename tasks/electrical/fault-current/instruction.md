You are a senior electrical engineer specializing in power systems protection.

## Problem

Calculate the initial symmetrical short-circuit current at a point in a radial
network using the IEC 60909 method. The network is supplied by a single source
through a series impedance.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Nominal system voltage (Un) | 11 | kV |
| Source resistance (Rs) | 0.5 | ohm |
| Source reactance (Xs) | 4.8 | ohm |
| Voltage factor (c) | 1.1 | - |

The voltage factor c = 1.1 is used for maximum short-circuit current calculation
at medium voltage levels per IEC 60909.

## Required

Calculate the following:
- Total impedance at the fault point (ohm)
- Initial symmetrical short-circuit current Ik'' (kA)
- X/R ratio

## Applicable Standards

- IEC 60909 — Short-circuit currents in three-phase AC systems (for reference)

Exact clause citation is optional.

## Constraints

- No internet access is available. Work from engineering knowledge only.
- Use the IEC 60909 method for initial symmetrical short-circuit current.

## Output Format

Show your step-by-step working in Markdown, including the formulas you use and
intermediate calculations. At the end of your solution, include a JSON block
with your final answers in exactly this format:

```json
{
  "total_impedance_ohm": <numeric_value>,
  "short_circuit_current_ka": <numeric_value>,
  "x_r_ratio": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
