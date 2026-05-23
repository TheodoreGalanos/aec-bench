You are a senior coastal/drainage engineer assessing whether a stormwater outfall will be adversely affected by tidal submergence under present-day and future sea level rise conditions.

## Problem

Determine the percentage of time a stormwater outfall pipe is submerged by tidal waters under present-day conditions and under a future sea level rise scenario. Calculate submergence as both a percentage and hours per day.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Outfall invert level | {{ outfall_invert_level_m }} | m AHD |
| Present-day mean sea level | {{ mean_sea_level_m }} | m AHD |
| Tidal amplitude (A) | {{ tidal_amplitude_m }} | m |
| Sea level rise projection | {{ sea_level_rise_m }} | m |
{% if tidal_period_hours is defined %}
| Tidal period | {{ tidal_period_hours }} | hours |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An outfall submergence calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Present-day submergence percentage (% of tidal cycle the outfall is submerged)
2. Future submergence percentage (after sea level rise)
3. Present-day hours per day the outfall is submerged
4. Future hours per day the outfall is submerged
5. Absolute increase in submergence percentage due to sea level rise

## Applicable Standards

- MfE Coastal Hazards Guidance 2024
- IPCC AR6 Sea Level Projections

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Model the tide as a simple sinusoidal function:
  - h(t) = MSL + A × sin(2π t / T)
  - where MSL = mean sea level, A = tidal amplitude, T = tidal period
{% if tidal_period_hours is not defined %}
  - Use 12.42 hours for semi-diurnal tides or an appropriate period for the tidal regime
{% endif %}
- The outfall is **submerged** when h(t) > outfall invert level
- Use the closed-form solution for the fraction of time a sinusoidal signal exceeds a threshold:
  1. Let x = (z_inv − MSL) / A, where z_inv is the outfall invert level
  2. If x ≥ 1: fraction submerged = 0 (invert always above tide)
  3. If x ≤ −1: fraction submerged = 1 (invert always below tide)
  4. Otherwise: **fraction submerged = 0.5 − (1/π) × arcsin(x)**
- For future conditions, shift MSL by the sea level rise: MSL_future = MSL + SLR
- Hours per day submerged = fraction × 24
- Submergence increase = future % − present %

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "present_submergence_percent": <numeric_value>,
  "future_submergence_percent": <numeric_value>,
  "present_hours_submerged_per_day": <numeric_value>,
  "future_hours_submerged_per_day": <numeric_value>,
  "submergence_increase_percent": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
