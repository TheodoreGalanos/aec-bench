# Catenary Sag Calculation (Incorrect)

## Given
- Span length: 250 m
- Conductor unit weight: 7.58 N/m
- Horizontal tension: 64500 N

## Calculation

I used the parabolic approximation instead of catenary equations:
sag = w * L^2 / (8 * H)
sag = 7.58 * 250^2 / (8 * 64500)
sag = 7.58 * 62500 / 516000
sag = 0.918 m (close but wrong method)

I also got the catenary constant wrong by using w/H instead of H/w:
c = w / H = 0.000117

```json
{
  "catenary_constant_m": 0.000117,
  "sag_m": 55.0,
  "conductor_length_m": 300.0
}
```
