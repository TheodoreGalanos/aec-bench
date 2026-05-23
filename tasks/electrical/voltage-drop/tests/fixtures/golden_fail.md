# Voltage Drop Calculation (Incorrect)

## Given
- Load current: 45 A
- Cable length: 80 m
- Cable resistance: 0.524 ohm/km

## Calculation

I used the simplified resistance-only method (no reactance, no power factor):
Vd = 2 x I x L x R / 1000
Vd = 2 x 45 x 80 x 0.524 / 1000
Vd = 3.7728 V

Also forgot sqrt(3) for three-phase and used single-phase formula.

```json
{
  "voltage_drop_v": 3.7728,
  "voltage_drop_pct": 0.9432,
  "compliance": 0
}
```
