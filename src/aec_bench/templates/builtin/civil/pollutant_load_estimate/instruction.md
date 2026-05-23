You are a senior civil engineer specializing in stormwater quality management and WSUD (Water Sensitive Urban Design).

## Problem

Estimate the annual pollutant loads from a catchment using the Event Mean Concentration (EMC) method, consistent with MUSIC modelling guidelines.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Catchment area (A) | {{ catchment_area_ha }} | ha |
| Mean annual rainfall (P) | {{ annual_rainfall_mm }} | mm |
| Runoff coefficient (C) | {{ runoff_coefficient }} | - |
{%- if emc_tss_mg_l is defined %}
| EMC — Total Suspended Solids | {{ emc_tss_mg_l }} | mg/L |
{%- endif %}
{%- if emc_tp_mg_l is defined %}
| EMC — Total Phosphorus | {{ emc_tp_mg_l }} | mg/L |
{%- endif %}
{%- if emc_tn_mg_l is defined %}
| EMC — Total Nitrogen | {{ emc_tn_mg_l }} | mg/L |
{%- endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A pollutant load calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Annual runoff volume V (m³/yr)
2. Annual Total Suspended Solids load (kg/yr)
3. Annual Total Phosphorus load (kg/yr)
4. Annual Total Nitrogen load (kg/yr)

## Applicable Standards

- MUSIC (Model for Urban Stormwater Improvement Conceptualisation) guidelines
- Australian Runoff Quality (ARQ)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the simple EMC method for pollutant load estimation:
  - **Annual runoff volume:** V = C × P × A × 10 (m³/yr)
    - C is the volumetric runoff coefficient (dimensionless, 0 to 1)
    - P is mean annual rainfall in mm
    - A is catchment area in ha
    - The factor 10 converts ha·mm to m³
  - **Pollutant load:** L = EMC × V / 1000 (kg/yr)
    - EMC is the event mean concentration in mg/L
    - V is the annual runoff volume in m³
    - The division by 1000 converts mg/L × m³ to kg
- Typical EMC values for Australian urban catchments (if not given directly):
  - Residential: TSS ≈ 150 mg/L, TP ≈ 0.35 mg/L, TN ≈ 2.0 mg/L
  - Commercial: TSS ≈ 170 mg/L, TP ≈ 0.40 mg/L, TN ≈ 2.5 mg/L
  - Industrial: TSS ≈ 200 mg/L, TP ≈ 0.45 mg/L, TN ≈ 3.0 mg/L
  - Parkland/open space: TSS ≈ 50 mg/L, TP ≈ 0.10 mg/L, TN ≈ 0.8 mg/L

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "annual_runoff_volume_m3": <numeric_value>,
  "tss_load_kg_yr": <numeric_value>,
  "tp_load_kg_yr": <numeric_value>,
  "tn_load_kg_yr": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
