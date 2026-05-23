You are a senior structural engineer specializing in structural loading and limit state design.

## Problem

Determine the serviceability limit state (SLS) load combinations for a structural member in accordance with AS/NZS 1170.0 Table 4.1.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Dead load (G) | {{ dead_load_kn }} | kN |
| Live load (Q) | {{ live_load_kn }} | kN |
{% if wind_serviceability_kn is defined %}
| Serviceability wind action (W_s) | {{ wind_serviceability_kn }} | kN |
{% endif %}
{% if load_category is defined %}
| Imposed-action category | {{ load_category }} | — |
{% endif %}
{% if archetype_description is defined %}

### Member Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An SLS load combination calculator is available at `/workspace/sls-load-combinations_calc.py`. Run it with:

```bash
python3 /workspace/sls-load-combinations_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Short-term combination factor (psi_s) from Table 4.1
2. Long-term combination factor (psi_l) from Table 4.1
3. Short-term SLS combination: G + psi_s × Q (kN)
4. Long-term SLS combination: G + psi_l × Q (kN)
5. Wind SLS combination: G + psi_s × Q + W_s (kN)
6. Governing (maximum) SLS combination value (kN)

## Applicable Standards

- AS/NZS 1170.0 — Structural design actions, Part 0: General principles (Table 4.1)
- AS 1170.1 — Structural design actions, Part 1: Permanent, imposed and other actions (imposed-action categories)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the SLS combination equations from AS/NZS 1170.0 Clause 4.2.2:
  - **Short-term:** G + psi_s × Q
  - **Long-term:** G + psi_l × Q
  - **Wind SLS:** G + psi_s × Q + W_s
- The combination factors psi_s (short-term) and psi_l (long-term) depend on the imposed-action category per AS 1170.1:
  - Category A (domestic/residential): psi_s = 0.7, psi_l = 0.4
  - Category B (offices): psi_s = 0.7, psi_l = 0.4
  - Category C (public assembly): psi_s = 0.7, psi_l = 0.6
  - Category D (shops/retail): psi_s = 0.7, psi_l = 0.4
  - Category E (storage): psi_s = 1.0, psi_l = 0.6
{% if load_category is not defined %}
- Determine the appropriate imposed-action category from the building use description, then look up the corresponding psi factors.
{% endif %}
{% if wind_serviceability_kn is not defined %}
- If no serviceability wind action is specified, assume W_s = 0 kN (sheltered or internal member).
{% endif %}
- The governing SLS combination is the maximum of all three combination values.

## Output Format

Show your step-by-step working in Markdown, including factor lookups and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "psi_s": <numeric_value>,
  "psi_l": <numeric_value>,
  "sls_short_term_kn": <numeric_value>,
  "sls_long_term_kn": <numeric_value>,
  "sls_wind_kn": <numeric_value>,
  "governing_sls_kn": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
