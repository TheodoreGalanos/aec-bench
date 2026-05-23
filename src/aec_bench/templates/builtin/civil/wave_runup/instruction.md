You are a senior coastal engineer specializing in wave runup and overtopping analysis for coastal structures.

## Problem

Determine the 2% exceedance wave runup height (Ru2%) on a coastal structure given the incident wave conditions and structure properties. Calculate the breaker parameter, runup height, and classify the wave regime.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Significant wave height (H_m0) | {{ wave_height_m }} | m |
{% if wave_period_s is defined %}
| Spectral wave period (T_m-1,0) | {{ wave_period_s }} | s |
{% endif %}
| Structure slope tan(α) | {{ structure_slope }} | - |
{% if roughness_factor is defined %}
| Roughness factor (γ_f) | {{ roughness_factor }} | - |
{% endif %}
{% if berm_factor is defined %}
| Berm factor (γ_b) | {{ berm_factor }} | - |
{% endif %}
{% if archetype_description is defined %}

### Structure Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A wave runup calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Breaker parameter (Iribarren number) ξ_m-1,0
2. 2% exceedance wave runup height Ru2% in metres
3. Wave regime — report as a numeric code: 1.0 = breaking/plunging, 2.0 = surging/non-breaking

## Applicable Standards

- EurOtop (2018) Manual on Wave Overtopping
- TAW (Technical Advisory Committee on Water Defences) Guidelines

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Assume head-on wave attack (γ_β = 1.0).
- Use the following procedure:
  1. **Spectral wavelength**:
     - L_m-1,0 = g × T_m-1,0² / (2π)
     - where g = 9.81 m/s²
  2. **Breaker parameter** (Iribarren-type):
     - ξ_m-1,0 = tan(α) / √(H_m0 / L_m-1,0)
  3. **Runup — breaking (plunging) expression**:
     - Ru2% / H_m0 = 1.65 × γ_b × γ_f × γ_β × ξ_m-1,0
  4. **Runup — maximum (surging) expression**:
     - Ru2% / H_m0 = γ_f × γ_β × (4.0 − 1.5 / √ξ_m-1,0)
  5. **Governing runup**: take the **minimum** of the two expressions above
  6. **Dimensional runup**: Ru2% = (Ru2% / H_m0) × H_m0
  7. **Regime classification**:
     - If the breaking expression governs → 1.0 (breaking/plunging)
     - If the maximum expression governs → 2.0 (surging/non-breaking)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "breaker_parameter": <numeric_value>,
  "runup_height_m": <numeric_value>,
  "regime": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
