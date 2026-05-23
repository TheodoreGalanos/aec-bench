You are a senior electrical engineer calculating overhead line capacitance.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Conductor radius | {{ conductor_radius_m }} | m |
| Phase spacing A-B | {{ phase_spacing_ab_m }} | m |
| Phase spacing B-C | {{ phase_spacing_bc_m }} | m |
| Phase spacing C-A | {{ phase_spacing_ca_m }} | m |
| Nominal line voltage | {{ nominal_voltage_kv }} | kV |
{% if frequency_hz is defined %}
| System frequency | {{ frequency_hz }} | Hz |
{% endif %}
| Line inductance | {{ inductance_mh_per_km }} | mH/km |

## Constraints

- Use `GMD = (Dab x Dbc x Dca)^(1/3)`.
- Use `C = 2 pi epsilon0 / ln(GMD / conductor_radius)`.
- Convert F/m to nF/km.
- Charging Mvar is for 100 km of three-phase line.
- Surge impedance is `sqrt(L / C)` using H/m and F/m.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "geometric_mean_distance_m": <numeric_value>,
  "capacitance_nf_per_km": <numeric_value>,
  "charging_mvar_per_100km": <numeric_value>,
  "surge_impedance_ohm": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
