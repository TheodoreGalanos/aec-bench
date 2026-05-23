# ABOUTME: Reference solution for catenary-sag task.
# ABOUTME: Computes conductor sag using catenary equations and writes output.md.

import math

H = 64500  # horizontal tension (N)
w = 7.58  # conductor unit weight (N/m)
L = 250  # span length (m)

c = H / w
sag = c * (math.cosh(L / (2 * c)) - 1)
length = 2 * c * math.sinh(L / (2 * c))

solution = f"""# Catenary Sag Calculation

## Given
- Span length: {L} m
- Conductor unit weight: {w} N/m
- Horizontal tension: {H} N

## Step 1: Catenary Constant
c = H / w = {H} / {w} = {c:.4f} m

## Step 2: Maximum Sag
sag = c * (cosh(L / (2c)) - 1)
sag = {c:.4f} * (cosh({L} / (2 * {c:.4f})) - 1)
sag = {sag:.4f} m

## Step 3: Conductor Length
length = 2c * sinh(L / (2c))
length = 2 * {c:.4f} * sinh({L} / (2 * {c:.4f}))
length = {length:.4f} m

```json
{{
  "catenary_constant_m": {c:.4f},
  "sag_m": {sag:.4f},
  "conductor_length_m": {length:.4f}
}}
```
"""

with open("/workspace/output.md", "w") as f:
    f.write(solution)

print(f"catenary_constant_m: {c:.4f}")
print(f"sag_m: {sag:.4f}")
print(f"conductor_length_m: {length:.4f}")
