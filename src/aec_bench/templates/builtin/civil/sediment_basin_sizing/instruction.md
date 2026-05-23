You are a senior civil engineer specializing in erosion and sediment control for construction sites.

## Problem

Size a construction sediment basin (Type {{ basin_type }}) in accordance with the Blue Book (*Managing Urban Stormwater: Soils and Construction*).

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Contributing catchment area (A) | {{ catchment_area_ha }} | ha |
{% if volumetric_runoff_coeff_m3_ha is defined %}
| Volumetric runoff coefficient (Cv) | {{ volumetric_runoff_coeff_m3_ha }} | m³/ha |
{% endif %}
{% if soil_loss_rate_m3_ha_yr is defined %}
| Soil loss rate (R) | {{ soil_loss_rate_m3_ha_yr }} | m³/ha/yr |
{% endif %}
| Clean-out interval (D) | {{ cleanout_interval_yr }} | years |
| Basin type | {{ basin_type }} | - |
{% if basin_type == "F" and permanent_pool_volume_m3 is defined %}
| Permanent pool volume (V_pool) | {{ permanent_pool_volume_m3 }} | m³ |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A sediment basin sizing calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Settling zone volume V_s (m³)
2. Sediment storage volume V_sed (m³)
3. Total basin volume V_total (m³)

## Applicable Standards

- Managing Urban Stormwater: Soils and Construction (Blue Book), Volume 1

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the Blue Book sediment basin sizing method:
  - **Settling zone volume:** V_s = Cv × A
    - Cv is the volumetric runoff coefficient (m³/ha), typically 150–400 depending on rainfall region
    - A is the contributing catchment area in hectares
  - **Sediment storage volume:** V_sed = R × A × D
    - R is the soil loss rate (m³/ha/yr)
    - D is the clean-out interval in years
  - **Total basin volume:** V_total = V_pool + V_s + V_sed
    - V_pool = 0 for Type D (dry) basins
    - V_pool is the permanent pool volume for Type F (wet) basins
- Type D basins are dry basins with settling and sediment storage zones only
- Type F basins include a permanent pool in addition to settling and sediment storage zones
- If Cv or R are not given directly, infer reasonable values from the soil type and rainfall region described in the site conditions

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "settling_volume_m3": <numeric_value>,
  "sediment_storage_volume_m3": <numeric_value>,
  "total_basin_volume_m3": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
