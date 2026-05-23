You are a senior electrical engineer specializing in power distribution and cable sizing.

## Problem

Calculate the voltage drop for a cable circuit and verify compliance with the allowable limits per AS/NZS 3008.1.1 and AS/NZS 3000:2018.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Cable size | {{ cable_size_mm2 }} | mm² |
| Cable route length | {{ length_m }} | m |
| Design load current | {{ load_current_a }} | A |
| Power factor | {{ power_factor }} | - |
{% if conductor_material is defined %}
| Conductor material | {{ conductor_material }} | - |
{% endif %}
| Circuit type | {{ circuit_type }} | - |
{% if archetype_description is defined %}

### Installation Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A voltage drop calculation tool is available at `/workspace/voltage-drop_calc.py`. Run it with:

```bash
python3 /workspace/voltage-drop_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Effective voltage drop rate Vc (mV/A/m) — from AS/NZS 3008.1.1 tables, adjusted for circuit type and power factor
2. Total voltage drop (V)
3. Voltage drop as percentage of nominal supply voltage (%)
4. Compliance assessment against the 5% limit (1.0 = pass, 0.0 = fail)

## Applicable Standards

- AS/NZS 3008.1.1 — Electrical installations — Selection of cables, Tables 42/44 for voltage drop values
- AS/NZS 3000:2018 Clause 3.6.2 — Maximum 5% voltage drop from point of supply to load
- IEC 60364-5-52 — Electrical installations of buildings — Selection and erection of electrical equipment

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the tabulated voltage drop method from AS/NZS 3008.1.1:
  - Look up the three-phase mV/A/m value (Vc) for the cable size and conductor material
  - For single-phase circuits: multiply the three-phase Vc by 2/√3 ≈ 1.1547
  - Adjust Vc by the power factor
  - Voltage drop: Vd = Vc × I × L / 1000
- Nominal supply voltages: single phase = 230 V, three phase = 400 V
- Voltage drop percentage: Vd% = (Vd / V_supply) × 100
- Compliant if Vd% ≤ 5.0%

## Output Format

Show your step-by-step working in Markdown, including the table lookup, adjustments, and final calculation. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "vc_mv_per_a_m": <numeric_value>,
  "voltage_drop_v": <numeric_value>,
  "voltage_drop_percent": <numeric_value>,
  "compliant": <1.0_or_0.0>
}
```

Write your complete solution to `/workspace/output.md`.
