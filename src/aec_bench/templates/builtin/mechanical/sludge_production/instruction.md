You are a senior mechanical engineer specializing in wastewater solids handling.

## Problem

Estimate activated sludge production from BOD removal, observed biomass yield, decay, and primary solids capture.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Flow rate | {{ flow_rate_m3_d }} | m3/d |
| Influent BOD | {{ influent_bod_mg_l }} | mg/L |
| Effluent BOD | {{ effluent_bod_mg_l }} | mg/L |
| Influent TSS | {{ influent_tss_mg_l }} | mg/L |
| Primary TSS removal | {{ primary_tss_removal_pct }} | % |
| Yield coefficient | {{ yield_coefficient }} | - |
| Decay coefficient | {{ decay_coefficient_d_inv }} | 1/d |
| SRT | {{ srt_days }} | d |
| VSS to TSS ratio | {{ vss_to_tss_ratio }} | - |

{% if archetype_description is defined %}
### Process Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A sludge production calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. BOD removed (kg/d)
2. Observed biomass yield (kg VSS/kg BOD removed)
3. Biomass production as VSS (kg/d)
4. Primary solids captured as TSS (kg/d)
5. Total sludge production as TSS (kg/d)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use BOD removed = flow x (influent BOD - effluent BOD) / 1000.
- Use observed yield = yield coefficient / (1 + decay coefficient x SRT).
- Use biomass VSS production = observed yield x BOD removed.
- Use biomass TSS production = biomass VSS production / VSS to TSS ratio.
- Use primary solids = flow x influent TSS x primary removal percent / 100000.
- Use total sludge production = biomass TSS production + primary solids.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "bod_removed_kg_d": <numeric_value>,
  "observed_yield_vss_per_bod": <numeric_value>,
  "biomass_production_kg_vss_d": <numeric_value>,
  "primary_solids_kg_tss_d": <numeric_value>,
  "total_sludge_kg_tss_d": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
