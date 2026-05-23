You are a senior mechanical engineer specializing in wastewater treatment process calculations.

## Problem

Calculate mixed liquor suspended solids inventory in an aeration basin.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Aeration volume | {{ aeration_volume_m3 }} | m3 |
| MLSS concentration | {{ mlss_concentration_mg_l }} | mg/L |
| MLVSS fraction | {{ mlvss_fraction }} | - |

{% if archetype_description is defined %}
### Process Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An MLSS inventory calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Total MLSS inventory (kg)
2. Estimated MLVSS inventory (kg)
3. Estimated inert suspended solids inventory (kg)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use MLSS inventory = aeration volume x MLSS concentration / 1000.
- Use MLVSS inventory = MLSS inventory x MLVSS fraction.
- Use inert solids inventory = MLSS inventory - MLVSS inventory.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "mlss_inventory_kg": <numeric_value>,
  "mlvss_inventory_kg": <numeric_value>,
  "inert_solids_inventory_kg": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
