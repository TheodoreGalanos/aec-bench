You are a senior mechanical engineer specializing in water and wastewater chemical dosing.

## Problem

Calculate treatment chemical feed requirements for a target active dose.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Process flow rate | {{ flow_rate_m3_d }} | m3/d |
| Target active dose | {{ target_dose_mg_l }} | mg/L |
| Product strength | {{ product_strength_pct }} | % |
| Product density | {{ product_density_kg_l }} | kg/L |

{% if archetype_description is defined %}
### Dosing Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A chemical dosing calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Active chemical mass feed rate (kg/d)
2. Commercial product mass feed rate (kg/d)
3. Commercial product volume feed rate (L/d)
4. Annual commercial product consumption (t/yr)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use active mass feed = flow rate x target dose / 1000.
- Use product mass feed = active mass feed / (product strength / 100).
- Use volume feed = product mass feed / product density.
- Use annual product consumption = product mass feed x 365 / 1000.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "active_mass_feed_kg_d": <numeric_value>,
  "product_mass_feed_kg_d": <numeric_value>,
  "volume_feed_l_d": <numeric_value>,
  "annual_product_consumption_t": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
