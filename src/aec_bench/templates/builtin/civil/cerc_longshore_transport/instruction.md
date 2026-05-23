You are a senior coastal engineer specializing in littoral processes and sediment transport.

## Problem

Calculate the longshore sediment transport rate using the CERC formula (USACE Coastal Engineering Manual / Shore Protection Manual).

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Breaking wave height (H_b) | {{ breaking_wave_height_m }} | m |
| Wave angle at breaking (α_b) | {{ wave_angle_at_breaking_deg }} | degrees |
{% if k_coefficient is defined %}
| CERC transport coefficient (K) | {{ k_coefficient }} | - |
{% endif %}
{% if sediment_density_kg_m3 is defined %}
| Sediment density (ρ_s) | {{ sediment_density_kg_m3 }} | kg/m³ |
{% endif %}
{% if water_density_kg_m3 is defined %}
| Water density (ρ_w) | {{ water_density_kg_m3 }} | kg/m³ |
{% endif %}
{% if porosity is defined %}
| Sediment porosity (p) | {{ porosity }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A longshore transport calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Wave energy flux at breaking (E × C_g)_b in W/m
2. Volumetric longshore transport rate Q_l in m³/year (absolute value)
3. Transport direction (1.0 = left-to-right looking shoreward, -1.0 = right-to-left)

## Applicable Standards

- USACE Coastal Engineering Manual (CEM)
- Shore Protection Manual (SPM)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the CERC formula with breaker index γ_b = 0.78:
  - Breaking depth: d_b = H_b / γ_b
  - Shallow water group velocity at breaking: C_gb = √(g × d_b)
  - Wave energy flux: (E × C_g)_b = ρ_w × g × H_b² × C_gb / 8
  - Longshore wave power component: P_ls = (E × C_g)_b × sin(2α_b) / 2
  - Immersed weight transport rate: I_l = K × P_ls
  - Volumetric transport rate: Q_l = I_l / ((ρ_s − ρ_w) × g × (1 − p))
  - Convert Q_l from m³/s to m³/year using 365.25 × 24 × 3600 seconds per year
- Use g = 9.81 m/s²
- Transport direction: positive α_b means transport is left-to-right looking shoreward (direction = 1.0); negative α_b means right-to-left (direction = -1.0)
- Report transport_rate_m3_yr as an absolute value

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "energy_flux_w_m": <numeric_value>,
  "transport_rate_m3_yr": <numeric_value>,
  "transport_direction": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
