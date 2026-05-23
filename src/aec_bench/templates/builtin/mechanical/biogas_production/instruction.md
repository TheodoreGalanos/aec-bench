You are a senior wastewater process engineer specializing in sludge digestion.

## Problem

Estimate daily biogas and methane production from volatile solids destruction.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Volatile solids feed | {{ volatile_solids_feed_kg_d }} | kg/d |
| Volatile solids destruction | {{ volatile_solids_destruction_pct }} | % |
| Biogas yield | {{ biogas_yield_m3_kg_vs }} | m3/kg VS destroyed |
| Methane fraction | {{ methane_fraction }} | - |

{% if archetype_description is defined %}
### Digestion Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A biogas production calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Volatile solids destroyed in kg/d
2. Biogas production in m3/d
3. Methane production in m3/d
4. Methane energy in kWh/d using 9.97 kWh/m3 methane

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use volatile solids destroyed = feed x destruction percentage / 100.
- Use biogas = volatile solids destroyed x biogas yield.
- Use methane = biogas x methane fraction.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "volatile_solids_destroyed_kg_d": <numeric_value>,
  "biogas_m3_d": <numeric_value>,
  "methane_m3_d": <numeric_value>,
  "methane_energy_kwh_d": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

