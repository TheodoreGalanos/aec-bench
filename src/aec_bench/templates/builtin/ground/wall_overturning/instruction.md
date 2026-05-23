You are a senior geotechnical engineer specializing in retaining wall design.

## Problem

Check the stability of a cantilever retaining wall against overturning about the toe using Rankine active earth pressure theory.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Wall stem height (H) | {{ wall_height_m }} | m |
| Base slab width (B) | {{ base_width_m }} | m |
| Stem thickness (t_stem) | {{ stem_thickness_m }} | m |
| Base slab thickness (t_base) | {{ base_thickness_m }} | m |
{% if backfill_friction_angle_deg is defined %}
| Backfill friction angle (φ') | {{ backfill_friction_angle_deg }} | degrees |
{% endif %}
{% if backfill_unit_weight_kn_m3 is defined %}
| Backfill unit weight (γ_s) | {{ backfill_unit_weight_kn_m3 }} | kN/m³ |
{% endif %}
| Concrete unit weight (γ_c) | {{ concrete_unit_weight_kn_m3 }} | kN/m³ |
{% if surcharge_kpa is defined %}
| Surcharge load (q) | {{ surcharge_kpa }} | kPa |
{% endif %}
{% if water_table_depth_m is defined %}
| Water table depth from wall top | {{ water_table_depth_m }} | m |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A retaining wall overturning calculation tool is available at `/workspace/wall-overturning_calc.py`. Run it with:

```bash
python3 /workspace/wall-overturning_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Rankine active earth pressure coefficient Ka
2. Total active force per metre of wall Pa (kN/m)
3. Overturning moment about the toe Mo (kNm/m)
4. Resisting moment about the toe Mr (kNm/m)
5. Factor of safety against overturning FoS

## Applicable Standards

- AS 4678 — Earth-retaining structures
- Eurocode 7 — Geotechnical design

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use Rankine active earth pressure theory:
  - **Active coefficient:** Ka = (1 - sin φ') / (1 + sin φ')
  - **Active force (triangular):** Pa = 0.5 × Ka × γ_s × H_total²
  - where H_total = wall stem height + base slab thickness
- The active force resultant acts at H_total / 3 from the base.
- If a surcharge q is present, the additional lateral force is Ka × q × H_total, acting at H_total / 2.
- If the water table is within the wall height, add hydrostatic pressure: P_w = 0.5 × γ_w × h_w² (γ_w = 9.81 kN/m³, h_w = submerged height).
- Wall geometry (cantilever L-wall from toe to heel):
  - Toe length = B / 3
  - Stem sits on the base starting at the toe length
  - Heel length = B - toe length - stem thickness
- Resisting moment about the toe includes:
  - Base slab self-weight (acting at B/2 from toe)
  - Stem self-weight (acting at toe_length + t_stem/2 from toe)
  - Backfill soil on the heel (acting at toe_length + t_stem + heel/2 from toe)
  - Vertical surcharge on the heel (if applicable)
- **Factor of safety against overturning:** FoS = Mr / Mo (minimum acceptable FoS = 2.0)

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "ka": <numeric_value>,
  "active_force_kn_m": <numeric_value>,
  "overturning_moment_knm_m": <numeric_value>,
  "resisting_moment_knm_m": <numeric_value>,
  "factor_of_safety_overturning": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
