You are a senior coastal engineer specializing in wave mechanics and shoreline processes.

## Problem

Determine the wave breaking parameters at a coastal site given the incident wave conditions and seabed geometry. Calculate the depth-limited breaking wave height, breaking depth, breaker type, and Iribarren number.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Incident wave height (H₀) | {{ wave_height_m }} | m |
{% if wave_period_s is defined %}
| Wave period (T) | {{ wave_period_s }} | s |
{% endif %}
| Water depth (d) | {{ water_depth_m }} | m |
{% if bottom_slope is defined %}
| Bottom slope (m) | {{ bottom_slope }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A wave breaking calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Depth-limited breaking wave height H_b (m)
2. Breaking depth d_b (m)
3. Breaker type (spilling, plunging, or surging) — report as a numeric code: 1.0 = spilling, 2.0 = plunging, 3.0 = surging
4. Iribarren number (surf similarity parameter) ξ

## Applicable Standards

- USACE Coastal Engineering Manual (CEM)
- Weggel (1972) breaker depth index relation

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following procedure:
  1. **Breaker depth index** (Weggel 1972 simplified):
     - γ_b = 1.56 / (1 + exp(−19.5 × m))
     - where m is the bottom slope
     - On a flat bottom (m → 0), γ_b → 0.78 (McCowan's solitary wave limit)
  2. **Depth-limited breaking wave height**:
     - H_b = γ_b × d
     - where d is the water depth at the location of interest
  3. **Breaking depth**:
     - d_b = H_b / γ_b
  4. **Deep-water wavelength**:
     - L₀ = g × T² / (2π)
     - where g = 9.81 m/s²
  5. **Iribarren number** (surf similarity parameter):
     - ξ = m / √(H₀ / L₀)
     - where H₀ is the incident wave height and L₀ is the deep-water wavelength
  6. **Breaker type classification**:
     - ξ < 0.5 → spilling (code 1.0)
     - 0.5 ≤ ξ < 3.3 → plunging (code 2.0)
     - ξ ≥ 3.3 → surging (code 3.0)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "breaking_wave_height_m": <numeric_value>,
  "breaking_depth_m": <numeric_value>,
  "breaker_type": <numeric_value>,
  "iribarren_number": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
