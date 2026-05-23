You are a senior electrical engineer specializing in overhead transmission line design and thermal rating.

## Problem

Calculate the steady-state thermal rating (ampacity) of a bare overhead conductor using the IEEE 738 heat balance method. The ampacity is the maximum current the conductor can carry continuously without exceeding its maximum allowable temperature.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Conductor outer diameter | {{ conductor_diameter_mm }} | mm |
| AC resistance at 25°C | {{ conductor_resistance_ohm_per_km }} | ohm/km |
| Maximum conductor temperature | {{ max_conductor_temp_c }} | °C |
| Ambient air temperature | {{ ambient_temp_c }} | °C |
| Wind speed | {{ wind_speed_m_s }} | m/s |
| Wind angle to conductor axis | {{ wind_angle_deg }} | degrees |
| Solar radiation intensity | {{ solar_radiation_w_m2 }} | W/m² |
{% if emissivity is defined %}
| Conductor emissivity | {{ emissivity }} | - |
{% endif %}
{% if absorptivity is defined %}
| Conductor absorptivity | {{ absorptivity }} | - |
{% endif %}
{% if archetype_description is defined %}

### Line Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A thermal rating calculation tool is available at `/workspace/static-thermal-rating_calc.py`. Run it with:

```bash
python3 /workspace/static-thermal-rating_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Convective heat loss per unit length (W/m) — using the maximum of natural and forced convection
2. Radiative heat loss per unit length (W/m)
3. Solar heat gain per unit length (W/m)
4. Steady-state ampacity (A) — from the heat balance equation

## Applicable Standards

- IEEE 738 — Standard for Calculating the Current-Temperature Relationship of Bare Overhead Conductors
- CIGRE TB 601 — Guide for Thermal Rating Calculations of Overhead Lines

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the IEEE 738 steady-state heat balance: qc + qr = qs + I²R, solved as I = sqrt((qc + qr - qs) / R)
- Evaluate air properties (density, viscosity, thermal conductivity) at the film temperature: Tfilm = (Tc + Ta) / 2
- Air density at sea level: rho = P × M / (R_gas × T_K) where P = 101325 Pa, M = 0.0289644 kg/mol, R_gas = 8.31447 J/(mol·K)
- Dynamic viscosity via Sutherland's law: mu = 1.458e-6 × T_K^1.5 / (T_K + 110.4) Pa·s
- Thermal conductivity of air: kf = 2.424e-2 + 7.477e-5 × Tf - 4.407e-9 × Tf² W/(m·°C)
- Natural convection: qcn = 3.645 × rho^0.5 × D^0.75 × (Tc - Ta)^1.25 W/m
- Forced convection (low Re): qc1 = Kangle × [1.01 + 1.35 × NRe^0.52] × kf × (Tc - Ta) W/m
- Forced convection (high Re): qc2 = Kangle × 0.0754 × NRe^0.6 × kf × (Tc - Ta) W/m
- Use qc = max(qcn, qc1, qc2)
- Wind angle factor: Kangle = 1.194 - cos(phi) + 0.194 × cos(2phi) + 0.368 × sin(2phi)
- Reynolds number: NRe = D × rho × Vw / mu
- Radiative cooling: qr = pi × D × sigma × epsilon × (Tc_K^4 - Ta_K^4) where sigma = 5.6704e-8 W/(m²·K⁴)
- Solar heat gain (perpendicular incidence): qs = alpha × Qse × D
- AC resistance at conductor temperature: R(T) = R(25°C) × [1 + 0.00403 × (T - 25)] where 0.00403 /°C is the temperature coefficient for aluminium
- Convert resistance from ohm/km to ohm/m before computing ampacity

## Output Format

Show your step-by-step working in Markdown, including air property calculations, each heat balance component, and the final ampacity derivation. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "convective_cooling_w_m": <numeric_value>,
  "radiative_cooling_w_m": <numeric_value>,
  "solar_heat_gain_w_m": <numeric_value>,
  "ampacity_a": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
