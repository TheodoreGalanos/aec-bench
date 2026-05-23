# ABOUTME: Reference solution for fault-current task.
# ABOUTME: Computes IEC 60909 initial symmetrical short-circuit current and writes output.md.

import math

Un_kv = 11  # nominal system voltage (kV)
Un = Un_kv * 1000  # convert to V
Rs = 0.5  # source resistance (ohm)
Xs = 4.8  # source reactance (ohm)
c = 1.1  # voltage factor

Zk = math.sqrt(Rs**2 + Xs**2)
Ik = (c * Un) / (math.sqrt(3) * Zk)
Ik_ka = Ik / 1000
xr = Xs / Rs

solution = f"""# Fault Current Calculation (IEC 60909)

## Given
- Nominal system voltage: {Un_kv} kV ({Un} V)
- Source resistance: {Rs} ohm
- Source reactance: {Xs} ohm
- Voltage factor: {c}

## Step 1: Total Impedance
Zk = sqrt(Rs^2 + Xs^2)
Zk = sqrt({Rs}^2 + {Xs}^2)
Zk = sqrt({Rs**2} + {Xs**2})
Zk = {Zk:.4f} ohm

## Step 2: Initial Symmetrical Short-Circuit Current
Ik'' = (c x Un) / (sqrt(3) x Zk)
Ik'' = ({c} x {Un}) / ({math.sqrt(3):.4f} x {Zk:.4f})
Ik'' = {Ik:.4f} A = {Ik_ka:.4f} kA

## Step 3: X/R Ratio
X/R = {Xs} / {Rs} = {xr:.4f}

```json
{{
  "total_impedance_ohm": {Zk:.4f},
  "short_circuit_current_ka": {Ik_ka:.4f},
  "x_r_ratio": {xr:.4f}
}}
```
"""

with open("/workspace/output.md", "w") as f:
    f.write(solution)

print(f"total_impedance_ohm: {Zk:.4f}")
print(f"short_circuit_current_ka: {Ik_ka:.4f}")
print(f"x_r_ratio: {xr:.4f}")
