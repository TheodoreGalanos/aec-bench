You are a senior geotechnical engineer specializing in in-situ testing and soil characterization.

## Problem

Derive soil parameters from Cone Penetration Test (CPT) data using Robertson (1990) normalized classification and standard correlations for strength parameters.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Cone resistance (qc) | {{ qc_mpa }} | MPa |
| Sleeve friction (fs) | {{ fs_kpa }} | kPa |
| Pore water pressure (u2) | {{ u2_kpa }} | kPa |
| Test depth | {{ depth_m }} | m |
{% if total_unit_weight_kn_m3 is defined %}
| Total unit weight (γ) | {{ total_unit_weight_kn_m3 }} | kN/m³ |
{% endif %}
{% if water_table_depth_m is defined %}
| Water table depth | {{ water_table_depth_m }} | m |
{% endif %}
{% if net_area_ratio is defined %}
| Net area ratio (a) | {{ net_area_ratio }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A CPT parameter derivation tool is available at `/workspace/cpt-parameter-derivation_calc.py`. Run it with:

```bash
python3 /workspace/cpt-parameter-derivation_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following parameters from the CPT data:

1. Corrected cone resistance qt (MPa): qt = qc + u2·(1 - a) / 1000
2. Friction ratio Rf (%): Rf = fs / qt × 100, where qt is in kPa
3. Total overburden stress σv0 = γ × depth, and effective overburden stress σ'v0 accounting for water table
4. Normalized cone resistance Qt = (qt - σv0) / σ'v0, where qt and stresses are in kPa
5. Normalized friction ratio Fr (%) = fs / (qt - σv0) × 100
6. Soil behavior type index Ic = √[(3.47 - log₁₀(Qt))² + (log₁₀(Fr) + 1.22)²]
7. If Ic > 2.6 (clay-like): undrained shear strength Su = (qt - σv0) / Nkt where Nkt = 14
8. If Ic ≤ 2.6 (sand-like): friction angle φ' = 17.6 + 11.0 × log₁₀(Qt) (Robertson & Campanella 1983)

## Applicable Standards

- Robertson, P.K. (1990) — Soil classification using the cone penetration test
- Lunne, T., Robertson, P.K. and Powell, J.J.M. (1997) — Cone Penetration Testing in Geotechnical Practice
- Robertson, P.K. and Campanella, R.G. (1983) — Interpretation of cone penetration tests

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use γ_w = 9.81 kN/m³ for pore water pressure calculations.
- Use atmospheric pressure Pa = 100 kPa as the reference for normalization.
- The corrected cone resistance accounts for the unequal end area effect: qt = qc + u2·(1 - a) / 1000, where u2 is in kPa and qc is in MPa.
- For the Ic boundary: Ic > 2.6 indicates clay-like behavior (report Su, set φ' = 0); Ic ≤ 2.6 indicates sand-like behavior (report φ', set Su = 0).
- Use Nkt = 14 for undrained shear strength estimation.
- Clamp Qt to a minimum of 1.0 and Fr to a minimum of 0.1 before computing log values.

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "qt_mpa": <numeric_value>,
  "friction_ratio_pct": <numeric_value>,
  "qt_norm": <numeric_value>,
  "fr_norm": <numeric_value>,
  "ic": <numeric_value>,
  "su_kpa": <numeric_value>,
  "phi_deg": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
