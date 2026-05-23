You are a senior mechanical engineer specializing in wastewater treatment process calculations.

## Problem

Calculate solids retention time for an activated sludge process.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Aeration volume | {{ aeration_volume_m3 }} | m3 |
| MLSS concentration | {{ mlss_concentration_mg_l }} | mg/L |
| WAS flow rate | {{ was_flow_m3_d }} | m3/d |
| WAS TSS concentration | {{ was_tss_mg_l }} | mg/L |
| Effluent TSS concentration | {{ effluent_tss_mg_l }} | mg/L |
| Effluent flow rate | {{ effluent_flow_m3_d }} | m3/d |

{% if archetype_description is defined %}
### Process Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An SRT calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Mass of solids in the aeration system (kg)
2. Mass of solids wasted per day (kg/d)
3. Mass of solids lost in effluent per day (kg/d)
4. Total daily solids loss (kg/d)
5. Solids retention time (days)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use solids inventory = aeration volume x MLSS / 1000.
- Use solids wasted = WAS flow x WAS TSS / 1000.
- Use effluent solids loss = effluent flow x effluent TSS / 1000.
- Use total solids loss = solids wasted + effluent solids loss.
- Use SRT = solids inventory / total solids loss.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "solids_in_system_kg": <numeric_value>,
  "solids_wasted_kg_d": <numeric_value>,
  "effluent_solids_loss_kg_d": <numeric_value>,
  "total_solids_loss_kg_d": <numeric_value>,
  "srt_days": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
