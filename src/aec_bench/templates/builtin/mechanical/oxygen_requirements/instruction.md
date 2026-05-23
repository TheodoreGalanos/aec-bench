You are a senior mechanical engineer specializing in wastewater treatment process design.

## Problem

Calculate activated sludge oxygen demand for carbonaceous oxidation, nitrogen oxidation, and denitrification credit.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Flow rate | {{ flow_rate_m3_d }} | m3/d |
| Influent BOD | {{ influent_bod_mg_l }} | mg/L |
| Effluent BOD | {{ effluent_bod_mg_l }} | mg/L |
| Influent TKN | {{ influent_tkn_mg_l }} | mg/L |
| Effluent TKN | {{ effluent_tkn_mg_l }} | mg/L |
| Sludge production | {{ sludge_production_kg_d }} | kg/d |
| Denitrified nitrogen | {{ denitrified_nitrogen_mg_l }} | mg/L |

{% if archetype_description is defined %}
### Process Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An oxygen demand calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. BOD removed (kg/d)
2. Carbonaceous oxygen demand after sludge credit (kg/d)
3. Nitrogenous oxygen demand (kg/d)
4. Denitrification oxygen credit (kg/d)
5. Total oxygen demand (kg/d)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use BOD removed = flow x (influent BOD - effluent BOD) / 1000.
- Use carbonaceous oxygen = BOD removed - 1.42 x sludge production, not less than zero.
- Use nitrogen removed = flow x (influent TKN - effluent TKN) / 1000.
- Use nitrogenous oxygen = 4.57 x nitrogen removed.
- Use denitrification credit = 2.86 x denitrified nitrogen load.
- Use total oxygen = carbonaceous + nitrogenous - denitrification credit, not less than zero.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "bod_removed_kg_d": <numeric_value>,
  "carbonaceous_oxygen_kg_d": <numeric_value>,
  "nitrogenous_oxygen_kg_d": <numeric_value>,
  "denitrification_credit_kg_d": <numeric_value>,
  "total_oxygen_kg_d": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
