You are a senior geotechnical engineer specializing in shallow foundation design.

## Task

Calculate the ultimate and allowable bearing capacity of a shallow foundation using **Meyerhof's (1963) general bearing capacity equation** with shape, depth, and inclination factors.

## Given Parameters

| Parameter | Value | Unit |
|-----------|-------|------|
{% if cohesion_kpa is defined %}| Effective cohesion (c') | {{ cohesion_kpa }} | kPa |
{% endif %}{% if friction_angle_deg is defined %}| Effective friction angle (φ') | {{ friction_angle_deg }} | degrees |
{% endif %}{% if unit_weight_kn_m3 is defined %}| Soil unit weight (γ) | {{ unit_weight_kn_m3 }} | kN/m³ |
{% endif %}| Footing width (B) | {{ footing_width_m }} | m |
| Footing length (L) | {{ footing_length_m }} | m |
| Embedment depth (Df) | {{ embedment_depth_m }} | m |
| Footing shape | {{ footing_shape }} | - |
{% if load_inclination_deg is defined and load_inclination_deg|float > 0 %}| Load inclination (θ) | {{ load_inclination_deg }} | degrees from vertical |
{% endif %}| Factor of safety | {{ factor_of_safety }} | - |

{% if archetype_description is defined %}
### Site Conditions

{{ archetype_description }}
{% endif %}

## Method

Use the **Meyerhof (1963)** general bearing capacity equation:

**q_u = c' × N_c × s_c × d_c × i_c + q × N_q × s_q × d_q × i_q + 0.5 × γ × B × N_γ × s_γ × d_γ × i_γ**

where q = γ × D_f (overburden pressure).

### Bearing Capacity Factors

- N_q = e^(π tan φ) × tan²(45 + φ/2)
- N_c = (N_q − 1) × cot φ  (N_c = 5.14 when φ = 0)
- N_γ = (N_q − 1) × tan(1.4φ)

### Shape Factors (K_p = tan²(45 + φ/2))

- s_c = 1 + 0.2 × K_p × (B/L)
- s_q = s_γ = 1 + 0.1 × K_p × (B/L) for φ > 10°; otherwise s_q = s_γ = 1

### Depth Factors

- d_c = 1 + 0.2 × √K_p × (D_f/B)
- d_q = d_γ = 1 + 0.1 × √K_p × (D_f/B) for φ > 10°; otherwise d_q = d_γ = 1

### Inclination Factors

- i_c = i_q = (1 − θ/90)²
- i_γ = (1 − θ/φ)² for φ > 0; otherwise i_γ = 0

For vertical loads (θ = 0): all inclination factors equal 1.

## Constraints

- No internet access is available.
- Use Meyerhof (1963) equations exactly as specified above.
- B is always the shorter dimension (B ≤ L).
- For strip footings, use B/L ≈ 0 (the L dimension is effectively infinite, so shape factors reduce accordingly — for practical purposes, the footing_length_m value is provided but B/L will be small).
- γ_w = 9.81 kN/m³ (if needed for water table corrections).

{% if tool_available %}
## Available Tool

A calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate all of the following:

1. Bearing capacity factors: N_c, N_q, N_γ
2. Shape factors: s_c, s_q, s_γ
3. Depth factors: d_c, d_q, d_γ
4. Inclination factors: i_c, i_q, i_γ
5. Ultimate bearing capacity q_u (kPa)
6. Allowable bearing capacity q_a = q_u / FoS (kPa)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "nc": <value>,
  "nq": <value>,
  "ngamma": <value>,
  "sc": <value>,
  "sq": <value>,
  "sgamma": <value>,
  "dc": <value>,
  "dq": <value>,
  "dgamma": <value>,
  "ic": <value>,
  "iq": <value>,
  "igamma": <value>,
  "ultimate_bearing_capacity_kpa": <value>,
  "allowable_bearing_capacity_kpa": <value>
}
```

Write your complete solution to `/workspace/output.md`.
