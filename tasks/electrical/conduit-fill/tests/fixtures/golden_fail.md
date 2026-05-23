# Conduit Fill Calculation (Incorrect)

## Given
- Conduit internal diameter: 50 mm
- Cat6 cables: 6 x 6.2 mm OD
- Fiber cables: 2 x 3.0 mm OD

## Calculation

I used the cable radius instead of diameter/2 and made unit errors:

Cat6 area = pi x 6.2^2 = 120.76 mm^2 (wrong - used diameter as radius)
Fiber area = pi x 3.0^2 = 28.27 mm^2

Total = 6 x 120.76 + 2 x 28.27 = 781.1 mm^2
Conduit area = pi x 50^2 = 7854.0 mm^2 (wrong - used diameter as radius)
Fill = 781.1 / 7854.0 x 100 = 9.95% (accidentally right percentage, wrong areas)

```json
{
  "total_cable_area_mm2": 781.1,
  "conduit_area_mm2": 7854.0,
  "fill_pct": 39.8,
  "compliance": 0
}
```
