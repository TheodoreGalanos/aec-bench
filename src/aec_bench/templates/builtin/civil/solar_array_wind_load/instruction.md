You are a senior civil/structural engineer specializing in wind loading for renewable energy structures.

## Problem

Calculate the wind loads on a ground-mounted solar PV array, including uplift pressure, downward pressure, per-module uplift force, and horizontal drag force.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design wind speed (V_des,θ) | {{ design_wind_speed_m_per_s }} | m/s |
{% if tilt_angle_deg is defined %}
| Array tilt angle | {{ tilt_angle_deg }} | degrees |
{% endif %}
| Hub height above ground | {{ array_height_m }} | m |
| Module width (slope direction) | {{ module_width_m }} | m |
| Module length (row direction) | {{ module_length_m }} | m |
| Modules wide (slope direction) | {{ num_modules_wide }} | - |
{% if row_position is defined %}
| Row position | {{ row_position }} | - |
{% endif %}
{% if air_density_kg_per_m3 is defined %}
| Air density (ρ) | {{ air_density_kg_per_m3 }} | kg/m³ |
{% endif %}
{% if archetype_description is defined %}

### Site Description

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A wind load calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Dynamic (velocity) pressure q in kPa
2. Net uplift (suction) pressure on the array in kPa
3. Net downward pressure on the array in kPa
4. Uplift force per module in kN
5. Horizontal drag force per metre of array row in kN/m

## Applicable Standards

- AS/NZS 1170.2 — Structural design actions, Part 2: Wind actions
- SEAOC PV2-2017 — Wind Design for Solar Arrays (net pressure coefficients)
- ASCE 7-22 Chapter 29 — Wind loads on other structures (ground-mounted PV)

## Methodology

- **Dynamic pressure** (AS/NZS 1170.2): q = 0.5 × ρ × V_des² (Pa), convert to kPa by dividing by 1000
- **Net pressure coefficients** (SEAOC PV2-2017): Use GCrn values that depend on tilt angle and row position (exposed end rows vs sheltered interior rows). Interior rows use approximately 60% of the exposed-row coefficients.
- **Approximate GCrn values for exposed panels:**

  | Tilt (°) | GCrn uplift | GCrn downforce |
  |----------|-------------|----------------|
  | 5        | 0.8         | 0.3            |
  | 10       | 1.0         | 0.5            |
  | 15       | 1.2         | 0.7            |
  | 20       | 1.4         | 0.9            |
  | 25       | 1.5         | 1.0            |
  | 30       | 1.6         | 1.1            |
  | 35       | 1.7         | 1.1            |
  | 45       | 1.8         | 1.2            |

  Interpolate linearly for intermediate tilt angles.

- **Uplift pressure**: p_uplift = q × GCrn_uplift
- **Downforce pressure**: p_down = q × GCrn_downforce
- **Uplift force per module**: F_uplift = p_uplift × module_width × module_length
- **Drag force per metre**: F_drag = q × C_drag × (num_modules_wide × module_width × sin(tilt)), where C_drag ≈ 1.3

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- The design wind speed provided is the site wind speed after all AS/NZS 1170.2 multipliers have been applied.
- Use standard air density of 1.2 kg/m³ unless otherwise specified.
- All forces and pressures should be reported as positive magnitudes.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "dynamic_pressure_kpa": <numeric_value>,
  "uplift_pressure_kpa": <numeric_value>,
  "downforce_pressure_kpa": <numeric_value>,
  "uplift_force_per_module_kn": <numeric_value>,
  "drag_force_per_m_kn": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
