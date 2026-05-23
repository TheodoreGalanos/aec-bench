You are a senior power systems engineer specialising in grid frequency response.

## Problem

Compute the P(f) droop control response for a generating unit operating at a
given frequency, and produce a professional droop curve chart for inclusion in
a technical report.

## Given

| Parameter                 | Value  | Unit |
|---------------------------|--------|------|
| Rated (base) power        | 175    | MW   |
| System nominal frequency  | 50     | Hz   |
| Deadband                  | +/- 0.1| Hz   |
| Droop setting             | 5      | %    |
| Minimum active power      | 0      | MW   |
| Maximum active power      | 175    | MW   |
| Reference power (Pref)    | 87.5   | MW   |
| Operating frequency       | 51.0   | Hz   |

## Required

Calculate the following:

1. **Droop slope** in MW/Hz
2. **Change in active power** (delta P) at the operating frequency in MW
3. **Active power output** at the operating frequency in MW (clamped to [Pmin, Pmax])

After computing the values, you **must** call the `create_chart` tool to
generate a P(f) droop curve chart and visually verify that:
- The curve shape is correct (flat in the deadband, linear slopes outside)
- The operating point is marked at the right location
- The delta-P annotation matches your calculation

## Constraints

Use the standard piecewise-linear P(f) droop model:

- **Slope** = Pbase / (Droop% / 100 x f_nominal)
- Within the deadband (f_nominal +/- deadband_hz): P = Pref (no response)
- Above the upper deadband edge (f > f_nominal + deadband_hz):
  P = Pref - Slope x (f - f_db_upper)
- Below the lower deadband edge (f < f_nominal - deadband_hz):
  P = Pref + Slope x (f_db_lower - f)
- Clamp the result: P = clamp(P, Pmin, Pmax)

## Output Format

Show your step-by-step working in Markdown, including the formulas you use and
intermediate calculations. At the end of your solution, include a JSON block
with your final answers in exactly this format:

```json
{
  "slope_mw_per_hz": <numeric_value>,
  "active_power_mw": <numeric_value>,
  "delta_p_mw": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
