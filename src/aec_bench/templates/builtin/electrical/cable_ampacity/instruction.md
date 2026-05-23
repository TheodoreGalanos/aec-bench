You are a senior electrical engineer specializing in power distribution and cable sizing.

## Problem

Calculate the derated current-carrying capacity (ampacity) for a cable installation, applying temperature and grouping derating factors per AS/NZS 3008.1.1 and IEC 60287.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Conductor size | {{ conductor_size_mm2 }} | mm² |
{% if insulation_type is defined %}
| Insulation type | {{ insulation_type }} | - |
{% endif %}
{% if installation_method is defined %}
| Installation method | {{ installation_method }} | - |
{% endif %}
| Ambient temperature | {{ ambient_temp_c }} | °C |
| Max conductor temperature | {{ max_conductor_temp_c }} | °C |
| Number of grouped circuits | {{ grouping_circuits }} | circuits |
{% if archetype_description is defined %}

### Installation Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A cable ampacity calculation tool is available at `/workspace/cable-ampacity_calc.py`. Run it with:

```bash
python3 /workspace/cable-ampacity_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Base current-carrying capacity (A) — from AS/NZS 3008.1.1 tables for the given conductor size, insulation type, and installation method
2. Temperature derating factor Ct
3. Grouping derating factor Cg
4. Final derated cable ampacity (A)

## Applicable Standards

- AS/NZS 3008.1.1 — Electrical installations — Selection of cables, Tables 4-15 for current-carrying capacity, Table 22 for grouping factors, Table 27 for temperature derating
- IEC 60287 — Electric cables — Calculation of the current rating
- IEC 60364-5-52 — Electrical installations of buildings — Selection and erection of electrical equipment

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following method to calculate derated ampacity:
  1. Look up the base ampacity from AS/NZS 3008.1.1 tables for the conductor size, insulation type, and installation method
  2. Calculate the temperature derating factor: Ct = sqrt((Tmax - Tamb) / (Tmax - Tref)) where Tref = 30°C
  3. Look up the grouping derating factor Cg from the table for the number of grouped circuits
  4. Final derated ampacity = base ampacity × Ct × Cg
- Reference ambient temperature for the base tables: Tref = 30°C
- Maximum conductor temperature: 90°C for XLPE insulation, 75°C for PVC insulation
- Grouping derating factors (number of circuits → factor): 1 → 1.00, 2 → 0.80, 3 → 0.70, 4 → 0.65, 5 → 0.60, 6 → 0.57, 7 → 0.54, 8 → 0.52, 9 → 0.50, 10 → 0.48, 11 → 0.46, 12 → 0.45

## Output Format

Show your step-by-step working in Markdown, including the table lookup, derating factor calculations, and final result. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "base_ampacity_a": <numeric_value>,
  "temp_derating_factor": <numeric_value>,
  "grouping_derating_factor": <numeric_value>,
  "derated_ampacity_a": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
