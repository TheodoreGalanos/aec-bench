You are a senior civil/dams engineer specializing in spillway hydraulics and dam safety.

## Problem

Calculate the discharge capacity of a spillway weir using the standard weir equation with pier and abutment contraction corrections.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Gross crest length (L) | {{ crest_length_m }} | m |
| Design head over crest (H) | {{ design_head_m }} | m |
{% if discharge_coefficient is defined %}
| Discharge coefficient (C) | {{ discharge_coefficient }} | - |
{% endif %}
{% if number_of_piers is defined %}
| Number of piers (N) | {{ number_of_piers }} | - |
{% endif %}
{% if pier_shape is defined %}
| Pier nose shape | {{ pier_shape }} | - |
{% endif %}
{% if abutment_shape is defined %}
| Abutment shape | {{ abutment_shape }} | - |
{% endif %}
{% if approach_channel_width_m is defined %}
| Approach channel width (B) | {{ approach_channel_width_m }} | m |
{% endif %}
{% if approach_depth_m is defined %}
| Approach flow depth (h_approach) | {{ approach_depth_m }} | m |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A spillway discharge calculation tool is available at `/workspace/spillway-weir-capacity_calc.py`. Run it with:

```bash
python3 /workspace/spillway-weir-capacity_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Effective crest length after pier and abutment contraction corrections L_eff (m)
2. Approach velocity head correction Va²/(2g) (m)
3. Total energy head over crest He (m)
4. Total spillway discharge capacity Q (m³/s)
5. Unit discharge per metre of effective crest q (m³/s/m)

## Applicable Standards

- USBR Design Standard No. 14 — Spillway design criteria
- USACE EM 1110-2-1603 — Hydraulic Design of Spillways

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the standard weir discharge equation:
  - **Q = C × L_eff × H_e^(3/2)**
  - Where C is the weir discharge coefficient in SI metric units
- Compute effective crest length with pier and abutment corrections:
  - **L_eff = L − 2 × (N × Kp + Ka) × H**
  - Pier contraction coefficients Kp: square = 0.02, round = 0.01, pointed = 0.00
  - Abutment contraction coefficients Ka: square = 0.20, rounded = 0.10, streamlined = 0.00
- Apply approach velocity head correction:
  - **Va = Q_initial / (B × h_approach)**
  - **Velocity head = Va² / (2g)**
  - **H_e = H + Va² / (2g)**
  - First compute Q_initial = C × L_eff × H^(3/2) without velocity head, then apply correction
- Use g = 9.81 m/s²
- Typical discharge coefficients (SI metric):
  - Ogee spillway: C ≈ 2.10–2.20
  - Broad-crested weir: C ≈ 1.50–1.80
- If no pier shape is given, assume round-nosed piers (Kp = 0.01)
- If no abutment shape is given, assume rounded abutments (Ka = 0.10)
- If no number of piers is given, assume N = 0
- Unit discharge: q = Q / L_eff

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "effective_crest_length_m": <numeric_value>,
  "approach_velocity_head_m": <numeric_value>,
  "total_energy_head_m": <numeric_value>,
  "discharge_m3_s": <numeric_value>,
  "unit_discharge_m3_s_per_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
