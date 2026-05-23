# Conduit Fill Calculation

## Given
- Conduit internal diameter: 50 mm
- Cat6 cables: 6 x 6.2 mm OD
- Fiber cables: 2 x 3.0 mm OD
- Maximum fill ratio: 40%

## Step 1: Cable Cross-Sectional Areas
Cat6 area (each) = pi x (6.2/2)^2 = pi x 9.61 = 30.1907 mm^2
Fiber area (each) = pi x (3.0/2)^2 = pi x 2.25 = 7.0686 mm^2

## Step 2: Total Cable Area
Total = 6 x 30.1907 + 2 x 7.0686
Total = 181.1443 + 14.1372
Total = 195.2814 mm^2

## Step 3: Conduit Area
Conduit area = pi x (50/2)^2 = pi x 625 = 1963.4954 mm^2

## Step 4: Fill Percentage
Fill = (195.2814 / 1963.4954) x 100 = 9.9456%

## Step 5: Compliance
9.95% is well below the 40% maximum fill ratio, so the installation complies.

```json
{
  "total_cable_area_mm2": 195.28,
  "conduit_area_mm2": 1963.50,
  "fill_pct": 9.95,
  "compliance": 1
}
```
