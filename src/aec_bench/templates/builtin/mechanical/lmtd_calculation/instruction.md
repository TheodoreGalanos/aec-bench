You are a senior mechanical engineer specializing in heat exchanger design.

## Problem

Calculate heat exchanger LMTD, corrected mean temperature difference, heat duty, and minimum approach temperature.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Hot inlet temperature | {{ hot_inlet_c }} | C |
| Hot outlet temperature | {{ hot_outlet_c }} | C |
| Cold inlet temperature | {{ cold_inlet_c }} | C |
| Cold outlet temperature | {{ cold_outlet_c }} | C |
| Overall heat transfer coefficient U | {{ overall_u_kw_m2_c }} | kW/m2.C |
| Heat transfer area | {{ heat_transfer_area_m2 }} | m2 |
| Correction factor F | {{ correction_factor }} | - |
| Flow arrangement | {{ flow_arrangement }} | - |

{% if archetype_description is defined %}
### Heat Exchanger Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An LMTD calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Terminal temperature differences (C)
2. Log mean temperature difference (C)
3. Corrected mean temperature difference (C)
4. Heat duty (kW)
5. Minimum terminal approach (C)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- For counterflow, use delta T1 = hot inlet - cold outlet and delta T2 = hot outlet - cold inlet.
- For parallel flow, use delta T1 = hot inlet - cold inlet and delta T2 = hot outlet - cold outlet.
- Use LMTD = (delta T1 - delta T2) / ln(delta T1 / delta T2).
- Use corrected MTD = LMTD x correction factor.
- Use heat duty = U x area x corrected MTD.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "delta_t1_c": <numeric_value>,
  "delta_t2_c": <numeric_value>,
  "lmtd_c": <numeric_value>,
  "corrected_mtd_c": <numeric_value>,
  "heat_duty_kw": <numeric_value>,
  "minimum_approach_c": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
