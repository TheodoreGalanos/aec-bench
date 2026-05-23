You are a senior geotechnical engineer specializing in retaining wall design.

## Problem

Check the bearing pressure under a retaining wall base, accounting for eccentricity of the resultant vertical load using Meyerhof's effective width method.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Base width (B) | {{ base_width_m }} | m |
| Total vertical load (V) | {{ total_vertical_load_kn_per_m }} | kN/m |
| Net moment about toe (M) | {{ net_moment_knm_per_m }} | kN.m/m |
{% if soil_cohesion_kpa is defined %}
| Foundation soil cohesion (c') | {{ soil_cohesion_kpa }} | kPa |
{% endif %}
{% if soil_friction_angle_deg is defined %}
| Foundation soil friction angle (phi') | {{ soil_friction_angle_deg }} | degrees |
{% endif %}
{% if soil_unit_weight_kn_m3 is defined %}
| Foundation soil unit weight (gamma) | {{ soil_unit_weight_kn_m3 }} | kN/m³ |
{% endif %}
{% if embedment_depth_m is defined %}
| Embedment depth (Df) | {{ embedment_depth_m }} | m |
{% endif %}
| Allowable bearing capacity (q_all) | {{ allowable_bearing_capacity_kpa }} | kPa |
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

## Method

Use the following procedure to check bearing pressure under the wall base:

### Step 1 — Eccentricity

Calculate the eccentricity of the resultant from the base centre:

**e = B/2 - M/V**

where M is the net moment about the toe and V is the total vertical load.

### Step 2 — Effective Base Width (Meyerhof)

**B' = B - 2e**

This reduces the base width to account for the eccentric loading.

### Step 3 — Maximum Bearing Pressure

**q_max = V / B'**

This is the maximum bearing pressure on the effective footing area (strip footing per metre run).

### Step 4 — Ultimate Bearing Capacity

Calculate the ultimate bearing capacity using Meyerhof's equation for a strip footing on the effective width:

**q_ult = c' x Nc x dc + q x Nq x dq + 0.5 x gamma x B' x Ngamma x dgamma**

where q = gamma x Df (overburden pressure).

#### Bearing Capacity Factors (Meyerhof)

- N_q = exp(pi x tan(phi)) x tan^2(45 + phi/2)
- N_c = (N_q - 1) x cot(phi)  [N_c = 5.14 when phi = 0]
- N_gamma = (N_q - 1) x tan(1.4 x phi)

#### Depth Factors (K_p = tan^2(45 + phi/2))

- d_c = 1 + 0.2 x sqrt(K_p) x (Df/B')
- d_q = d_gamma = 1 + 0.1 x sqrt(K_p) x (Df/B') for phi > 10 degrees; otherwise d_q = d_gamma = 1

### Step 5 — Factor of Safety

**FoS = q_all / q_max**

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use Meyerhof's effective width method (B' = B - 2e) to handle eccentric loading.
- The wall base acts as a strip footing (shape factors = 1.0, inclination factors = 1.0).
- Use the Meyerhof bearing capacity factors and depth factors as specified above.
- For phi = 0 (undrained clay): Nc = 5.14, Nq = 1.0, Ngamma = 0.0.
- gamma_w = 9.81 kN/m³ (if needed).

{% if tool_available %}
## Available Tool

A calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Eccentricity of the resultant e (m)
2. Effective base width B' (m)
3. Maximum bearing pressure q_max (kPa)
4. Ultimate bearing capacity q_ult (kPa)
5. Factor of safety against bearing failure FoS

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "eccentricity_m": <numeric_value>,
  "effective_width_m": <numeric_value>,
  "max_bearing_pressure_kpa": <numeric_value>,
  "ultimate_bearing_capacity_kpa": <numeric_value>,
  "factor_of_safety": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
