# Voltage Drop Calculation

## Given
- Circuit type: Three-phase
- Load current: 45 A
- Cable length: 80 m (one way)
- Cable resistance: 0.524 ohm/km
- Cable reactance: 0.08 ohm/km
- Power factor: 0.85
- System voltage: 400 V

## Step 1: Calculate sin(phi)
cos(phi) = 0.85
sin(phi) = sin(acos(0.85)) = 0.5268

## Step 2: Voltage Drop
Using the three-phase impedance method:
Vd = sqrt(3) x I x L x (R x cos(phi) + X x sin(phi)) / 1000
Vd = 1.7321 x 45 x 80 x (0.524 x 0.85 + 0.08 x 0.5268) / 1000
Vd = 1.7321 x 45 x 80 x (0.4454 + 0.0421) / 1000
Vd = 1.7321 x 45 x 80 x 0.4876 / 1000
Vd = 3.0400 V

## Step 3: Percentage
Vd% = 3.0400 / 400 x 100 = 0.7600%

## Step 4: Compliance
0.76% is less than 5% limit, so the cable complies.

```json
{
  "voltage_drop_v": 3.04,
  "voltage_drop_pct": 0.76,
  "compliance": 1
}
```
