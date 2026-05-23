You are a senior electrical engineer calculating overhead line parameters.

## Problem

Calculate the geometric mean distance, equivalent bundle GMR, and per-phase inductance for a reduced transposed three-phase line.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Conductor GMR | {{ conductor_gmr_m }} | m |
| Phase spacing A-B | {{ phase_spacing_ab_m }} | m |
| Phase spacing B-C | {{ phase_spacing_bc_m }} | m |
| Phase spacing C-A | {{ phase_spacing_ca_m }} | m |
{% if bundle_count is defined %}
| Bundle count | {{ bundle_count }} | - |
{% endif %}
| Bundle spacing | {{ bundle_spacing_m }} | m |
{% if archetype_description is defined %}

### Site Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A line inductance calculation tool is available at `/workspace/line-inductance_calc.py`. Run it with:

```bash
python3 /workspace/line-inductance_calc.py --help
```
{% endif %}

## Required

Calculate:

1. Geometric mean distance, `GMD = (Dab x Dbc x Dca)^(1/3)`
2. Equivalent bundle GMR in mm
3. Per-phase inductance, `L = 0.2 x ln(GMD / GMR_eq)` mH/km

## Constraints

- For a single conductor, `GMR_eq = GMR`.
- For two subconductors, `GMR_eq = sqrt(GMR x bundle_spacing)`.
- For three subconductors, `GMR_eq = (GMR x bundle_spacing^2)^(1/3)`.
- For four subconductors, `GMR_eq = 1.09 x (GMR x bundle_spacing^3)^(1/4)`.

## Output Format

Show your working in Markdown. At the end, include a JSON block with exactly these keys:

```json
{
  "geometric_mean_distance_m": <numeric_value>,
  "equivalent_gmr_mm": <numeric_value>,
  "inductance_mh_per_km": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
