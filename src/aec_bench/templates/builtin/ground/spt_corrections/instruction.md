You are a senior geotechnical engineer specializing in site investigation.

## Problem

Apply standard corrections to a raw SPT N-value to obtain the energy-corrected N60 and the overburden-normalised (N1)60 values, using the Liao & Whitman (1986) procedure.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Raw SPT blow count (N) | {{ raw_n_value }} | blows/300mm |
| Effective overburden stress (σ'v) | {{ effective_overburden_kpa }} | kPa |
{% if hammer_type is defined %}
| Hammer type | {{ hammer_type }} | - |
{% endif %}
{% if borehole_diameter_mm is defined %}
| Borehole diameter | {{ borehole_diameter_mm }} | mm |
{% endif %}
{% if sampler_type is defined %}
| Sampler type | {{ sampler_type }} | - |
{% endif %}
| Rod length | {{ rod_length_m }} | m |
{% if archetype_description is defined %}

### Test Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An SPT correction calculation tool is available at `/workspace/spt_corrections_calc.py`. Run it with:

```bash
python3 /workspace/spt_corrections_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following correction factors and corrected values:

1. Energy correction factor CE
2. Borehole diameter correction factor CB
3. Sampler correction factor CS
4. Rod length correction factor CR
5. Energy-corrected N-value: N60 = N × CE × CB × CS × CR
6. Overburden correction factor: CN = min(sqrt(Pa/σ'v), 2.0) where Pa = 100 kPa
7. Normalised corrected value: (N1)60 = CN × N60

## Applicable Standards

- Liao, S.S.C. and Whitman, R.V. (1986) — Overburden correction factors for SPT in sand
- ASTM D1586 — Standard Test Method for Standard Penetration Test

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following correction factor tables:
  - CE: auto=1.33, safety=0.96, donut=0.79
  - CB: 65mm=1.00, 115mm=1.00, 150mm=1.05, 200mm=1.15
  - CS: with liner=1.00, without liner=1.20
  - CR: 3-4m=0.75, 4-6m=0.85, 6-10m=0.95, >10m=1.00
- Cap CN at 2.0 maximum

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "ce": <numeric_value>,
  "cb": <numeric_value>,
  "cs": <numeric_value>,
  "cr": <numeric_value>,
  "n60": <numeric_value>,
  "cn": <numeric_value>,
  "n1_60": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
