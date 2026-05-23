You are a senior mechanical engineer specializing in process reactor sizing.

## Problem

Calculate required plug flow reactor volume for an isothermal constant-density first-order reaction.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Volumetric flow rate Q | {{ volumetric_flow_m3_h }} | m3/h |
| Inlet concentration C0 | {{ inlet_concentration_kmol_m3 }} | kmol/m3 |
| Required conversion X | {{ required_conversion_pct }} | % |
| First-order rate constant k | {{ rate_constant_h_inv }} | 1/h |

{% if archetype_description is defined %}
### Reactor Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A PFR sizing calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Molar feed rate of limiting reactant (kmol/h)
2. Outlet concentration at required conversion (kmol/m3)
3. Required space time (h)
4. Required plug flow reactor volume (m3)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Convert percent conversion to decimal conversion X.
- Use molar feed = Q x C0.
- Use outlet concentration = C0 x (1 - X).
- Use first-order PFR space time tau = -ln(1 - X) / k.
- Use required volume = Q x tau.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "molar_feed_kmol_h": <numeric_value>,
  "outlet_concentration_kmol_m3": <numeric_value>,
  "space_time_h": <numeric_value>,
  "required_volume_m3": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
