# Catenary Sag Calculation

## Given
- Span length: 250 m
- Conductor unit weight: 7.58 N/m
- Horizontal tension: 64500 N

## Step 1: Catenary Constant

The catenary constant is defined as:
c = H / w = 64500 / 7.58 = 8509.2348 m

## Step 2: Maximum Sag

Using the catenary equation:
sag = c * (cosh(L / (2c)) - 1)
sag = 8509.2348 * (cosh(250 / 17018.4696) - 1)
sag = 8509.2348 * (cosh(0.01469) - 1)
sag = 8509.2348 * 0.000107895
sag = 0.9181 m

## Step 3: Conductor Length

length = 2c * sinh(L / (2c))
length = 2 * 8509.2348 * sinh(0.01469)
length = 17018.4696 * 0.014691
length = 250.0090 m

```json
{
  "catenary_constant_m": 8509.2348,
  "sag_m": 0.9181,
  "conductor_length_m": 250.009
}
```
