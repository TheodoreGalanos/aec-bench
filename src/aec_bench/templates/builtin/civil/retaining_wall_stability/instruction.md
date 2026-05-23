You are a senior geotechnical engineer specializing in retaining wall design and stability analysis per Australian and European standards.

## Problem

Check the external stability of a rectangular gravity retaining wall against sliding, overturning, and bearing capacity failure. The wall retains a horizontal backfill and is founded at ground level on the foundation soil.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Wall height (H) | {{ wall_height_m }} | m |
| Base width (B) | {{ base_width_m }} | m |
| Wall stem thickness (t) | {{ wall_thickness_m }} | m |
{% if concrete_unit_weight_kn_m3 is defined %}
| Concrete unit weight (gamma_c) | {{ concrete_unit_weight_kn_m3 }} | kN/m3 |
{% endif %}
{% if backfill_friction_angle_deg is defined %}
| Backfill friction angle (phi') | {{ backfill_friction_angle_deg }} | degrees |
{% endif %}
{% if backfill_unit_weight_kn_m3 is defined %}
| Backfill unit weight (gamma_s) | {{ backfill_unit_weight_kn_m3 }} | kN/m3 |
{% endif %}
{% if backfill_cohesion_kpa is defined %}
| Backfill cohesion (c') | {{ backfill_cohesion_kpa }} | kPa |
{% endif %}
{% if surcharge_kpa is defined %}
| Uniform surcharge (q) | {{ surcharge_kpa }} | kPa |
{% endif %}
{% if foundation_friction_angle_deg is defined %}
| Foundation friction angle (phi_f) | {{ foundation_friction_angle_deg }} | degrees |
{% endif %}
{% if foundation_cohesion_kpa is defined %}
| Foundation cohesion (c_f) | {{ foundation_cohesion_kpa }} | kPa |
{% endif %}
{% if base_friction_ratio is defined %}
| Base friction ratio (delta / phi_f) | {{ base_friction_ratio }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A retaining wall stability calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Active earth pressure coefficient Ka
2. Factor of safety against sliding along the base
3. Factor of safety against overturning about the toe
4. Factor of safety against bearing capacity failure
5. Eccentricity of the resultant force from the base centre e (m)
6. Maximum base contact pressure q_max (kPa)

## Wall Configuration

The wall is a rectangular gravity wall. The stem (thickness t) is positioned at the **front** (toe side) of the base. Backfill soil of depth H sits on the heel portion (B - t) of the base behind the stem. The toe is at the front of the base.

## Applicable Standards

- AS 4678 — Earth Retaining Structures
- Eurocode 7 — Geotechnical Design

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use **Rankine theory** for active earth pressure (horizontal backfill):
  - Ka = tan^2(45 - phi'/2)
- **Active pressure at depth z:** sigma_a = Ka * gamma_s * z + Ka * q - 2c' * sqrt(Ka)
  - If total active force is negative (cohesion dominates), use Pa = 0
- **Sliding check:**
  - Resisting force = V * tan(delta) + c_b * B
  - delta = base_friction_ratio * phi_f (interface friction angle in radians)
  - c_b = base_friction_ratio * c_f (base adhesion)
  - FoS_sliding = Resisting force / Horizontal active force
- **Overturning check:**
  - Stabilising moments about the toe: wall weight, soil on heel, surcharge on heel
  - Overturning moments about the toe: active earth pressure components
  - FoS_overturning = Stabilising moment / Overturning moment
- **Bearing check:**
  - Eccentricity e = B/2 - x_resultant, where x_resultant = M_net / V_total
  - Maximum base pressure: q_max = V/B * (1 + 6e/B) for e <= B/6
  - If e > B/6: q_max = V / (3 * x_resultant)
  - Ultimate bearing capacity (Terzaghi strip footing at surface): q_ult = c_f * Nc + 0.5 * gamma_s * B' * Ngamma
  - Use effective width B' = B - 2|e| for eccentric loading
  - Bearing capacity factors: Nq = e^(2*(3pi/4 - phi_f/2)*tan(phi_f)) / (2*cos^2(45 + phi_f/2)), Nc = (Nq-1)/tan(phi_f), Ngamma = 2*(Nq+1)*tan(phi_f)
  - For phi_f = 0: Nc = 5.14, Nq = 1.0, Ngamma = 0
  - FoS_bearing = q_ult / q_max
- Use gamma_w = 9.81 kN/m3 if needed
- Report FoS = 99.99 where the driving force or moment is zero

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "ka": <numeric_value>,
  "fos_sliding": <numeric_value>,
  "fos_overturning": <numeric_value>,
  "fos_bearing": <numeric_value>,
  "eccentricity_m": <numeric_value>,
  "max_base_pressure_kpa": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
