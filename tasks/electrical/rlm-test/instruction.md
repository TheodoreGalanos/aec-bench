# Voltage Drop Calculation (RLM Test)

Calculate the three-phase voltage drop for a cable with the following parameters:

| Parameter | Value |
|-----------|-------|
| Current (I) | 45 A |
| Cable length (L) | 80 m |
| Resistance (R) | 0.524 Ω/km |
| Reactance (X) | 0.08 Ω/km |
| Power factor (pf) | 0.85 |
| System voltage (V) | 400 V |

Use the formula: Vd = √3 × I × L × (R × cos φ + X × sin φ) / 1000

Calculate:
1. `voltage_drop_v` — the voltage drop in volts
2. `voltage_drop_pct` — the voltage drop as a percentage of system voltage
3. `compliance` — 1 if voltage drop ≤ 5%, else 0

Write your final answer as a JSON code block in `/workspace/output.md`:

```json
{
    "voltage_drop_v": <value>,
    "voltage_drop_pct": <value>,
    "compliance": <value>
}
```
