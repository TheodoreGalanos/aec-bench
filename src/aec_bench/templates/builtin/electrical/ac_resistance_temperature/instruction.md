You are a senior electrical engineer specializing in power transmission and conductor design.

## Problem

Calculate the AC resistance of a conductor at its operating temperature, accounting for the temperature correction of DC resistance and the skin effect factor per IEC 60287-1-1.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| DC resistance at 20 °C | {{ dc_resistance_20c_ohm_per_km }} | ohm/km |
{% if conductor_material is defined %}
| Conductor material | {{ conductor_material }} | - |
{% endif %}
| Operating temperature | {{ operating_temp_c }} | °C |
| System frequency | {{ frequency_hz }} | Hz |
{% if archetype_description is defined %}

### Installation Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A calculation tool is available at `/workspace/ac-resistance-temperature_calc.py`. Run it with:

```bash
python3 /workspace/ac-resistance-temperature_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. DC resistance at operating temperature (ohm/km)
2. Skin effect factor ys (dimensionless)
3. AC resistance at operating temperature (ohm/km)

## Applicable Standards

- IEC 60287-1-1 — Electric cables — Calculation of the current rating — Current rating equations and calculation of losses
- IEEE 738 — Standard for Calculating the Current-Temperature of Bare Overhead Conductors

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the IEC 60287-1-1 method:
  1. DC resistance at temperature: R_dc(T) = R_dc_20 * [1 + alpha_20 * (T - 20)]
  2. Temperature coefficient alpha_20: copper = 0.00393 /°C, aluminium = 0.00403 /°C
  3. Skin effect argument: xs^2 = 8 * pi * f * 1e-7 * ks / R_dc(T) where R_dc(T) is in ohm/m and ks = 1 for round stranded conductors
  4. Skin effect factor: ys = xs^4 / (192 + 0.8 * xs^4)
  5. AC resistance: R_ac = R_dc(T) * (1 + ys) — proximity effect yp = 0 for single isolated conductors

## Output Format

Show your step-by-step working in Markdown, including the temperature correction, skin effect calculation, and final AC resistance. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "dc_resistance_at_temp_ohm_per_km": <numeric_value>,
  "skin_effect_factor": <numeric_value>,
  "ac_resistance_ohm_per_km": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
