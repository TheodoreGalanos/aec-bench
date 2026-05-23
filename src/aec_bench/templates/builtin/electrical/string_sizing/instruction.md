You are a senior electrical engineer specializing in solar photovoltaic system design.

## Problem

Determine the maximum and minimum number of PV modules per string based on temperature-corrected voltage limits, in accordance with AS/NZS 5033 and IEC 62548.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Module Voc at STC | {{ voc_stc_v }} | V |
| Module Vmp at STC | {{ vmp_stc_v }} | V |
| Temperature coefficient of Voc | {{ temp_coeff_voc_pct_per_c }} | %/degC |
| Temperature coefficient of Vmp | {{ temp_coeff_vmp_pct_per_c }} | %/degC |
{% if site_min_temp_c is defined %}
| Site minimum temperature | {{ site_min_temp_c }} | degC |
{% endif %}
{% if site_max_temp_c is defined %}
| Site maximum temperature | {{ site_max_temp_c }} | degC |
{% endif %}
| Inverter max DC voltage | {{ inverter_max_dc_voltage_v }} | V |
| Inverter min MPPT voltage | {{ inverter_min_mppt_voltage_v }} | V |
| Inverter nominal MPPT voltage | {{ inverter_nominal_mppt_voltage_v }} | V |
{% if archetype_description is defined %}

### Site Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A string sizing calculation tool is available at `/workspace/string-sizing_calc.py`. Run it with:

```bash
python3 /workspace/string-sizing_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Temperature-corrected Voc at site minimum temperature (V)
2. Temperature-corrected Vmp at site maximum temperature (V)
3. Maximum number of modules per string (limited by inverter max DC voltage at coldest conditions)
4. Minimum number of modules per string (to maintain voltage above inverter min MPPT at hottest conditions)

## Applicable Standards

- AS/NZS 5033 — Installation and safety requirements for photovoltaic (PV) arrays
- IEC 62548 — Photovoltaic (PV) arrays — Design requirements

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following temperature correction formulas per AS/NZS 5033:
  - Voc_corrected_cold = Voc_stc x (1 + (temp_coeff_voc / 100) x (T_min - 25))
  - Vmp_corrected_hot = Vmp_stc x (1 + (temp_coeff_vmp / 100) x (T_max - 25))
- Maximum modules per string = floor(inverter_max_dc_voltage / Voc_corrected_cold)
- Minimum modules per string = ceil(inverter_min_mppt_voltage / Vmp_corrected_hot)
- Temperature coefficients are expressed as %/degC (negative values, since voltage decreases with increasing temperature)
- STC reference temperature = 25 degC

## Output Format

Show your step-by-step working in Markdown, including the temperature corrections and string sizing calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "voc_corrected_cold_v": <numeric_value>,
  "vmp_corrected_hot_v": <numeric_value>,
  "max_modules_per_string": <integer_value>,
  "min_modules_per_string": <integer_value>
}
```

Write your complete solution to `/workspace/output.md`.
