You are a senior coastal engineer specializing in wave mechanics and nearshore hydrodynamics.

## Problem

Calculate wave properties using linear (Airy) wave theory by solving the dispersion relation for the given wave period and water depth.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Wave period (T) | {{ wave_period_s }} | s |
| Water depth (d) | {{ water_depth_m }} | m |
{% if wave_height_m is defined %}
| Wave height (H) | {{ wave_height_m }} | m |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A linear wave theory calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Wavelength L (m)
2. Wave phase celerity C (m/s)
3. Group velocity C_g (m/s)
4. Wave steepness S = H / L (dimensionless)
5. Relative depth d/L (dimensionless)

## Applicable Standards

- USACE Coastal Engineering Manual (CEM) Part II Chapter 1

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following procedure:
  1. **Deep-water wavelength** (initial estimate):
     - L₀ = g × T² / (2π)
     - where g = 9.81 m/s²
  2. **Solve the dispersion relation** iteratively (Newton-Raphson):
     - L = L₀ × tanh(2πd / L)
     - Define f(L) = L − L₀ × tanh(2πd / L)
     - Derivative: f'(L) = 1 + L₀ × (2πd / L²) / cosh²(2πd / L)
     - Update: L_{n+1} = L_n − f(L_n) / f'(L_n)
     - Start from L₀ and iterate until convergence (|L_{n+1} − L_n| < 10⁻⁶)
  3. **Wave celerity**:
     - C = L / T
  4. **Group velocity**:
     - k = 2π / L
     - n = 0.5 × (1 + 2kd / sinh(2kd))
     - C_g = n × C
  5. **Wave steepness**:
     - S = H / L
  6. **Relative depth**:
     - d/L (classify: > 0.5 deep, < 0.05 shallow, else intermediate)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "wavelength_m": <numeric_value>,
  "wave_celerity_m_per_s": <numeric_value>,
  "group_velocity_m_per_s": <numeric_value>,
  "wave_steepness": <numeric_value>,
  "relative_depth": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
