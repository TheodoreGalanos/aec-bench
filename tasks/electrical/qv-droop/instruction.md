You are a senior power systems engineer specialising in reactive power and voltage control.

## Problem

Compute the Q(V) droop control response for a generating unit operating at a
given voltage, and produce a professional droop curve chart for inclusion in
a technical report.

## Given

| Parameter                       | Value   | Unit  |
|---------------------------------|---------|-------|
| Rated (base) reactive power     | 69.5    | MVAr  |
| Base voltage                    | 1.0     | p.u.  |
| Deadband                        | +/- 0.01| p.u.  |
| Droop setting                   | 4       | %     |
| Minimum reactive power (Qmin)   | -69.5   | MVAr  |
| Maximum reactive power (Qmax)   | 69.5    | MVAr  |
| Normal reactive power (Qnormal) | 0       | MVAr  |
| Reference voltage (Vref)        | 1.0     | p.u.  |
| Operating voltage               | 0.97    | p.u.  |

## Required

Calculate the following:

1. **Droop slope** in MVAr/p.u.
2. **Change in reactive power** (delta Q) at the operating voltage in MVAr
3. **Reactive power output** at the operating voltage in MVAr (clamped to [Qmin, Qmax])

After computing the values, you **must** call the `create_chart` tool to
generate a Q(V) droop curve chart and visually verify that:
- The curve shape is correct (flat in the deadband, linear slopes outside)
- The operating point is marked at the right location
- The delta-Q annotation matches your calculation
- Positive Q (injection) is shown for low voltage, negative Q (absorption) for high voltage

## Constraints

Use the standard piecewise-linear Q(V) droop model:

- **Slope** = Qbase / (Droop% / 100 x Vbase)
- Within the deadband (Vref +/- deadband_pu): Q = Qnormal (no response)
- Below the lower deadband edge (V < Vref - deadband_pu):
  Q = Qnormal + Slope x (V_db_lower - V)   *(positive Q = reactive power injection for voltage support)*
- Above the upper deadband edge (V > Vref + deadband_pu):
  Q = Qnormal - Slope x (V - V_db_upper)   *(negative Q = reactive power absorption for voltage reduction)*
- Clamp the result: Q = clamp(Q, Qmin, Qmax)

## Output Format

Show your step-by-step working in Markdown, including the formulas you use and
intermediate calculations. At the end of your solution, include a JSON block
with your final answers in exactly this format:

```json
{
  "slope_mvar_per_pu": <numeric_value>,
  "reactive_power_mvar": <numeric_value>,
  "delta_q_mvar": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
