You are a senior electrical engineer specializing in battery energy storage system design.

## Problem

Size a battery energy storage system (BESS) by calculating the nominal power rating, required energy capacity, beginning-of-life (BOL) installed capacity, and usable energy per IEC 62933 and IEEE 2030.2.1.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Required discharge power | {{ power_requirement_mw }} | MW |
| Discharge duration | {{ discharge_duration_hours }} | h |
{% if depth_of_discharge_pct is defined %}
| Depth of discharge (DoD) | {{ depth_of_discharge_pct }} | % |
{% endif %}
{% if round_trip_efficiency_pct is defined %}
| Round-trip efficiency (η_rt) | {{ round_trip_efficiency_pct }} | % |
{% endif %}
| Degradation allowance | {{ degradation_allowance_pct }} | % |
{% if archetype_description is defined %}

### Application Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A BESS sizing calculation tool is available at `/workspace/bess-sizing_calc.py`. Run it with:

```bash
python3 /workspace/bess-sizing_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Nominal power rating (MW) — the rated discharge power of the BESS
2. Required energy capacity (MWh) — the energy that must be delivered during the discharge period
3. Beginning-of-life installed capacity (MWh) — the total nameplate energy capacity accounting for DoD, round-trip efficiency, and degradation
4. Usable energy at BOL (MWh) — the energy actually available after DoD and efficiency losses

## Applicable Standards

- IEC 62933 — Electrical energy storage (EES) systems
- IEEE 2030.2.1 — Guide for design, operation, and maintenance of battery energy storage systems

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Nominal power rating equals the required discharge power: P_nominal = P_required
- Required energy: E_required = P × t_discharge (MWh)
- Beginning-of-life capacity must account for depth of discharge, round-trip efficiency, and degradation:
  - E_bol = E_required / (DoD × η_rt × (1 − degradation))
  - Where DoD and η_rt are expressed as fractions (e.g., 90% → 0.90)
- Usable energy at BOL: E_usable = E_bol × DoD × η_rt
- All percentage inputs (DoD, efficiency, degradation) are given as percentages and must be converted to fractions for calculation

## Output Format

Show your step-by-step working in Markdown, including the energy requirement, BOL capacity derivation, and usable energy computation. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "nominal_power_mw": <numeric_value>,
  "required_energy_mwh": <numeric_value>,
  "bol_capacity_mwh": <numeric_value>,
  "usable_energy_mwh": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
