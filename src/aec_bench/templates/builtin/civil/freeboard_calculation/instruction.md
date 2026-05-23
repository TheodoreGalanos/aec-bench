You are a senior coastal/flood engineer specializing in freeboard design for coastal and flood-prone structures.

## Problem

Calculate the required total freeboard allowance and minimum crest (or floor) level for a coastal or flood structure.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Design water level (DWL) | {{ design_water_level_m }} | m above datum |
{% if wave_allowance_m is defined %}
| Wave overtopping allowance | {{ wave_allowance_m }} | m |
{% endif %}
{% if slr_allowance_m is defined %}
| Sea level rise allowance | {{ slr_allowance_m }} | m |
{% endif %}
{% if construction_tolerance_m is defined %}
| Construction tolerance | {{ construction_tolerance_m }} | m |
{% endif %}
{% if safety_margin_m is defined %}
| Safety margin | {{ safety_margin_m }} | m |
{% endif %}
{% if archetype_description is defined %}

### Structure and Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A freeboard calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Total freeboard allowance (m) — the sum of all component allowances
2. Minimum crest or floor level (m above datum) — design water level plus total freeboard

## Applicable Standards

- NZS 4404:2010 (Land Development and Subdivision Infrastructure)
- MfE Guidance 2024 (Coastal Hazards and Climate Change)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the component-based freeboard approach:
  - Total freeboard = wave_allowance + slr_allowance + construction_tolerance + safety_margin
  - Minimum crest level = design_water_level + total_freeboard
- Wave overtopping allowance depends on wave height and structure type (typical range 0.3–1.0 m)
- Sea level rise allowance depends on planning horizon (typical range 0.1–1.0 m)
- Construction tolerance is typically 0.05–0.15 m
- Safety margin depends on consequence category (typical range 0.15–0.50 m)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "total_freeboard_m": <numeric_value>,
  "minimum_crest_level_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
