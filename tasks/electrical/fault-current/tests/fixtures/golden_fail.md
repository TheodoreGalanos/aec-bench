# Fault Current Calculation (Incorrect)

## Given
- Nominal system voltage: 11 kV
- Source resistance: 0.5 ohm
- Source reactance: 4.8 ohm
- Voltage factor: 1.1

## Calculation

I forgot to convert kV to V and used wrong voltage factor:

Zk = Rs + Xs = 0.5 + 4.8 = 5.3 ohm (should be sqrt of sum of squares)
Ik = (1.0 x 11) / (1.732 x 5.3) = 1.198 kA (wrong units, wrong c, wrong Z)

```json
{
  "total_impedance_ohm": 5.3,
  "short_circuit_current_ka": 1.198,
  "x_r_ratio": 4.8
}
```
