# Fault Current Calculation (IEC 60909)

## Given
- Nominal system voltage: 11 kV (11000 V)
- Source resistance: 0.5 ohm
- Source reactance: 4.8 ohm
- Voltage factor: 1.1

## Step 1: Total Impedance
Zk = sqrt(Rs^2 + Xs^2)
Zk = sqrt(0.25 + 23.04)
Zk = sqrt(23.29)
Zk = 4.8260 ohm

## Step 2: Initial Symmetrical Short-Circuit Current
Ik'' = (c x Un) / (sqrt(3) x Zk)
Ik'' = (1.1 x 11000) / (1.7321 x 4.8260)
Ik'' = 12100 / 8.3576
Ik'' = 1447.57 A = 1.4476 kA

## Step 3: X/R Ratio
X/R = 4.8 / 0.5 = 9.6

```json
{
  "total_impedance_ohm": 4.826,
  "short_circuit_current_ka": 1.4476,
  "x_r_ratio": 9.6
}
```
