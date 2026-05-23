You are a senior geotechnical engineer specializing in retaining wall design and earth pressure analysis per Australian standards.

## Problem

Calculate the active and passive lateral earth pressure coefficients and forces acting on a retaining wall using Rankine theory. Determine the resultant forces, overturning moment, and hydrostatic water force where applicable.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Wall height (H) | {{ wall_height_m }} | m |
{% if friction_angle_deg is defined %}
| Effective friction angle (phi') | {{ friction_angle_deg }} | degrees |
{% endif %}
{% if cohesion_kpa is defined %}
| Effective cohesion (c') | {{ cohesion_kpa }} | kPa |
{% endif %}
{% if unit_weight_kn_m3 is defined %}
| Soil unit weight (gamma) | {{ unit_weight_kn_m3 }} | kN/m3 |
{% endif %}
{% if surcharge_kpa is defined %}
| Uniform surcharge (q) | {{ surcharge_kpa }} | kPa |
{% endif %}
{% if water_table_depth_m is defined %}
| Water table depth below ground surface | {{ water_table_depth_m }} | m |
{% endif %}
{% if backfill_slope_deg is defined %}
| Backfill slope angle (beta) | {{ backfill_slope_deg }} | degrees |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A lateral earth pressure calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Active earth pressure coefficient Ka
2. Passive earth pressure coefficient Kp
3. Total active earth pressure force per unit wall length Pa (kN/m)
4. Total passive earth pressure force per unit wall length Pp (kN/m)
5. Active overturning moment about the wall base Ma (kNm/m)
6. Hydrostatic water force per unit wall length Pw (kN/m)

## Applicable Standards

- AS 4678 — Earth Retaining Structures
- Rankine, W.J.M. (1857) — On the Stability of Loose Earth

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use **Rankine theory** for earth pressure coefficients:
  - Horizontal backfill: Ka = tan^2(45 - phi'/2), Kp = tan^2(45 + phi'/2)
  - Inclined backfill (slope beta): Ka = cos(beta) * (cos(beta) - sqrt(cos^2(beta) - cos^2(phi'))) / (cos(beta) + sqrt(cos^2(beta) - cos^2(phi')))
- **Active pressure at depth z:** sigma_a = Ka * gamma * z + Ka * q - 2c' * sqrt(Ka)
- **Passive pressure at depth z:** sigma_p = Kp * gamma * z + Kp * q + 2c' * sqrt(Kp)
- **Water table handling:**
  - Above the water table: use total (bulk) unit weight gamma
  - Below the water table: use effective (buoyant) unit weight gamma' = gamma - gamma_w
  - Hydrostatic water pressure acts independently: Pw = 0.5 * gamma_w * h_sub^2 (where h_sub = wall height below water table)
  - Water pressure is NOT multiplied by Ka; it acts equally in all directions (Pascal's law)
- **Total active force:** sum of effective earth pressure components over full wall height
- **Overturning moment:** sum of each active force component multiplied by its lever arm from the base, plus water force moment
- If total active force is negative (cohesion dominates), report Pa = 0 and Ma = 0
- If no water table is specified or water table is at full wall height, report Pw = 0
- Use gamma_w = 9.81 kN/m3
- For phi' = 0 (purely cohesive soil): Ka = Kp = 1.0

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "ka": <numeric_value>,
  "kp": <numeric_value>,
  "active_force_kn_per_m": <numeric_value>,
  "passive_force_kn_per_m": <numeric_value>,
  "active_moment_knm_per_m": <numeric_value>,
  "water_force_kn_per_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
