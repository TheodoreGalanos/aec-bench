You are a senior coastal engineer specializing in wave mechanics and nearshore transformations.

## Problem

Determine the wave transformation from deep to shallow water at a coastal site. Calculate the shoaling coefficient, refraction coefficient, and the resulting nearshore wave height.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Deep-water wave height (H₀) | {{ deep_water_wave_height_m }} | m |
{% if wave_period_s is defined %}
| Wave period (T) | {{ wave_period_s }} | s |
{% endif %}
| Nearshore depth (d) | {{ nearshore_depth_m }} | m |
{% if deep_water_wave_angle_deg is defined %}
| Deep-water wave angle to contour (θ₀) | {{ deep_water_wave_angle_deg }} | degrees |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A wave shoaling calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Shoaling coefficient K_s (dimensionless)
2. Refraction coefficient K_r (dimensionless)
3. Nearshore wave height H (m)

## Applicable Standards

- USACE Coastal Engineering Manual (CEM)
- Fenton & McKee (1990) explicit wavelength approximation

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following procedure:
  1. **Deep-water wavelength**:
     - L₀ = g × T² / (2π)
     - where g = 9.81 m/s²
  2. **Local wavelength** via Fenton & McKee (1990) explicit approximation:
     - σ = 2π / T
     - kd = (σ² × d / g) × [coth((σ² × d / g)^(3/4))]^(2/3)
     - where coth(x) = 1 / tanh(x)
     - k = kd / d, L = 2π / k
     - This avoids iterative solution of the dispersion relation (< 1.5% error).
  3. **Phase and group velocity**:
     - C = L / T (local phase celerity)
     - n = 0.5 × (1 + 2kd / sinh(2kd))
     - C_g = n × C (local group velocity)
  4. **Deep-water group velocity**:
     - C_g0 = g × T / (4π)
  5. **Shoaling coefficient**:
     - K_s = √(C_g0 / C_g)
  6. **Refraction** via Snell's law:
     - C₀ = L₀ / T (deep-water phase celerity)
     - sin(θ) / C = sin(θ₀) / C₀
     - K_r = √(cos(θ₀) / cos(θ))
  7. **Nearshore wave height**:
     - H = H₀ × K_s × K_r

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "shoaling_coefficient": <numeric_value>,
  "refraction_coefficient": <numeric_value>,
  "nearshore_wave_height_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
