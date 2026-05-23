# ABOUTME: Reference solution for voltage-drop task.
# ABOUTME: Computes three-phase voltage drop using impedance method and writes output.md.

import math

current = 45  # load current (A)
L = 80  # cable length one way (m)
R = 0.524  # cable resistance (ohm/km)
X = 0.08  # cable reactance (ohm/km)
pf = 0.85  # power factor
V = 400  # system voltage (V)

sin_phi = math.sin(math.acos(pf))
Vd = math.sqrt(3) * current * L * (R * pf + X * sin_phi) / 1000
Vd_pct = Vd / V * 100
compliance = 1 if Vd_pct <= 5.0 else 0

solution = f"""# Voltage Drop Calculation

## Given
- Circuit type: Three-phase
- Load current: {current} A
- Cable length: {L} m
- Cable resistance: {R} ohm/km
- Cable reactance: {X} ohm/km
- Power factor: {pf}
- System voltage: {V} V

## Step 1: Calculate sin(phi)
sin(phi) = sin(acos({pf})) = {sin_phi:.4f}

## Step 2: Voltage Drop
Vd = sqrt(3) x I x L x (R x cos(phi) + X x sin(phi)) / 1000
Vd = {math.sqrt(3):.4f} x {current} x {L} x ({R} x {pf} + {X} x {sin_phi:.4f}) / 1000
Vd = {Vd:.4f} V

## Step 3: Percentage
Vd% = {Vd:.4f} / {V} x 100 = {Vd_pct:.4f}%

## Step 4: Compliance
{Vd_pct:.4f}% <= 5.0% -> compliance = {compliance}

```json
{{
  "voltage_drop_v": {Vd:.4f},
  "voltage_drop_pct": {Vd_pct:.4f},
  "compliance": {compliance}
}}
```
"""

with open("/workspace/output.md", "w") as f:
    f.write(solution)

print(f"voltage_drop_v: {Vd:.4f}")
print(f"voltage_drop_pct: {Vd_pct:.4f}")
print(f"compliance: {compliance}")
