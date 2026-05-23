# ABOUTME: Reference solution for conduit-fill task.
# ABOUTME: Computes conduit fill percentage from cable geometry and writes output.md.

import math

conduit_id = 50.0  # conduit internal diameter (mm)
cat6_count = 6
cat6_od = 6.2  # Cat6 cable outer diameter (mm)
fiber_count = 2
fiber_od = 3.0  # fiber cable outer diameter (mm)
max_fill = 40.0  # maximum fill ratio (%)

cat6_area = math.pi * (cat6_od / 2) ** 2
fiber_area = math.pi * (fiber_od / 2) ** 2
total_cable_area = cat6_count * cat6_area + fiber_count * fiber_area
conduit_area = math.pi * (conduit_id / 2) ** 2
fill_pct = (total_cable_area / conduit_area) * 100
compliance = 1 if fill_pct <= max_fill else 0

solution = f"""# Conduit Fill Calculation

## Given
- Conduit internal diameter: {conduit_id} mm
- Cat6 cables: {cat6_count} x {cat6_od} mm OD
- Fiber cables: {fiber_count} x {fiber_od} mm OD
- Maximum fill ratio: {max_fill}%

## Step 1: Cable Cross-Sectional Areas
Cat6 area (each) = pi x (6.2/2)^2 = pi x 9.61 = {cat6_area:.4f} mm^2
Fiber area (each) = pi x (3.0/2)^2 = pi x 2.25 = {fiber_area:.4f} mm^2

## Step 2: Total Cable Area
Total = 6 x {cat6_area:.4f} + 2 x {fiber_area:.4f}
Total = {cat6_count * cat6_area:.4f} + {fiber_count * fiber_area:.4f}
Total = {total_cable_area:.4f} mm^2

## Step 3: Conduit Area
Conduit area = pi x (50/2)^2 = pi x 625 = {conduit_area:.4f} mm^2

## Step 4: Fill Percentage
Fill = ({total_cable_area:.4f} / {conduit_area:.4f}) x 100 = {fill_pct:.4f}%

## Step 5: Compliance
{fill_pct:.2f}% <= {max_fill}% -> compliance = {compliance}

```json
{{
  "total_cable_area_mm2": {total_cable_area:.4f},
  "conduit_area_mm2": {conduit_area:.4f},
  "fill_pct": {fill_pct:.4f},
  "compliance": {compliance}
}}
```
"""

with open("/workspace/output.md", "w") as f:
    f.write(solution)

print(f"total_cable_area_mm2: {total_cable_area:.4f}")
print(f"conduit_area_mm2: {conduit_area:.4f}")
print(f"fill_pct: {fill_pct:.4f}")
print(f"compliance: {compliance}")
