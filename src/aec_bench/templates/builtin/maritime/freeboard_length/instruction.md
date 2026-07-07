You are a senior naval architect specializing in classification society rule compliance.

## Problem

Calculate the IACS Freeboard length L_LL for a ship under the Harmonised Common Structural Rules (CSR-H).

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Total length on a waterline at 85% of the least moulded depth | {{ total_length_on_85pct_depth_waterline_m }} | m |
{% if has_rudder_stock is defined %}
| Has rudder stock | {{ has_rudder_stock }} | - |
{% endif %}
{% if stem_to_rudder_stock_axis_distance_m is defined %}
| Length from the fore side of the stem to the axis of the rudder stock, on that waterline | {{ stem_to_rudder_stock_axis_distance_m }} | m |
{% endif %}
{% if archetype_description is defined %}

### Vessel Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A Freeboard length calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Freeboard length L_LL (m)

## Applicable Standards

- IACS Harmonised Common Structural Rules (CSR-H), edition 01 JUL 2025, Pt 1 Ch 1 Sec 4 §3.1.2

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Quote from Pt 1 Ch 1 Sec 4 §3.1.2: "The freeboard length L_LL, in m, is to be taken as 96% of the total length on a waterline at 85% of the least moulded depth measured from the top of the keel, or as the length from the fore side of the stem to the axis of the rudder stock on that waterline, if that be greater. For ships without a rudder stock, the length L_LL is to be taken as 96% of the waterline at 85% of the least moulded depth."
- If the ship has a rudder stock, L_LL is the GREATER of (a) 96% of the total length on the 85%-depth waterline and (b) the measured length from the fore side of the stem to the axis of the rudder stock on that waterline.
- If the ship has no rudder stock (e.g. azimuth thrusters), L_LL = 96% of the total length on the 85%-depth waterline.
- Ships with unusual (concave) stem contours are out of scope for this calculation — assume a conventional stem contour unless stated otherwise.

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answer in exactly this format:

```json
{
  "freeboard_length_LLL_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
