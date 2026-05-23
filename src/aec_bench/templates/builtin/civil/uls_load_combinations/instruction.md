You are a senior structural engineer specializing in structural design actions and load combination analysis.

## Problem

Determine all ultimate limit state (ULS) load combinations for a structural element and identify the governing design action, in accordance with AS/NZS 1170.0 Table 4.1.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Dead load (G) | {{ dead_load_kn }} | kN |
| Live load (Q) | {{ live_load_kn }} | kN |
{% if wind_ultimate_kn is defined %}
| Ultimate wind action (W_u) | {{ wind_ultimate_kn }} | kN |
{% endif %}
{% if earthquake_load_kn is defined %}
| Earthquake action (E) | {{ earthquake_load_kn }} | kN |
{% endif %}
{% if load_category is defined %}
| Imposed action category | {{ load_category }} | - |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A ULS load combination calculation tool is available at `/workspace/uls-load-combinations_calc.py`. Run it with:

```bash
python3 /workspace/uls-load-combinations_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following ULS load combinations:

1. Permanent only: 1.35 * G (kN)
2. Permanent + imposed: 1.2 * G + 1.5 * Q (kN)
3. Permanent + wind + imposed companion: 1.2 * G + psi_c * Q + W_u (kN)
4. Permanent + wind (uplift/overturning): 0.9 * G + W_u (kN)
5. Permanent + earthquake + imposed companion: G + psi_E * Q + E (kN)
6. Governing ULS design action Ed = max of all combinations (kN)

## Applicable Standards

- AS/NZS 1170.0:2002 — Structural design actions, General principles (Table 4.1)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the AS/NZS 1170.0 Table 4.1 ULS load combination formulas:
  - **Combination 1:** Ed = 1.35 * G
  - **Combination 2:** Ed = 1.2 * G + 1.5 * Q
  - **Combination 3:** Ed = 1.2 * G + psi_c * Q + W_u
  - **Combination 4:** Ed = 0.9 * G + W_u (for uplift or overturning)
  - **Combination 5:** Ed = G + psi_E * Q + E
- Combination factors depend on the imposed action category:
  - Categories A-D: psi_c = 0.4, psi_E = 0.3
  - Category E (storage): psi_c = 0.6, psi_E = 0.6
{% if load_category is not defined %}
- If the imposed action category is not given, use Category A (psi_c = 0.4, psi_E = 0.3).
{% endif %}
{% if wind_ultimate_kn is not defined %}
- If the ultimate wind action is not given, consider whether wind is relevant for the site and adopt an appropriate value.
{% endif %}
{% if earthquake_load_kn is not defined %}
- If the earthquake action is not given, consider whether earthquake loading is relevant for the site and adopt an appropriate value.
{% endif %}
- The governing ULS design action is the maximum of all five combinations.

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "uls_permanent_kn": <numeric_value>,
  "uls_imposed_kn": <numeric_value>,
  "uls_wind_kn": <numeric_value>,
  "uls_wind_uplift_kn": <numeric_value>,
  "uls_earthquake_kn": <numeric_value>,
  "governing_uls_kn": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
