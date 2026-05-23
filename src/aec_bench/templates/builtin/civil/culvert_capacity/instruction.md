You are a senior civil engineer specializing in hydraulic design and culvert analysis.

## Problem

Determine the headwater depth under inlet control and outlet control for a circular culvert, and identify the controlling condition using HDS-5 methodology.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Culvert diameter (D) | {{ culvert_diameter_m }} | m |
| Culvert length (L) | {{ culvert_length_m }} | m |
| Culvert slope (S) | {{ culvert_slope_m_per_m }} | m/m |
| Design flow (Q) | {{ design_flow_m3_s }} | m³/s |
{% if culvert_configuration is defined %}
| Culvert configuration | {{ culvert_configuration }} | - |
{% endif %}
| Tailwater depth (TW) | {{ tailwater_depth_m }} | m |
{% if invert_elevation_m is defined %}
| Inlet invert elevation | {{ invert_elevation_m }} | m AHD |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A culvert capacity calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Headwater depth above inlet invert under inlet control (m)
2. Headwater depth above inlet invert under outlet control (m)
3. Controlling condition (1.0 = inlet control, 2.0 = outlet control)
4. Headwater elevation at the controlling condition (m AHD)

## Applicable Standards

- HDS-5: Hydraulic Design of Highway Culverts (FHWA)
- ARR: Australian Rainfall and Runoff

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use HDS-5 methodology for circular culverts in SI units.

### Inlet Control (HDS-5)

Compute the flow intensity parameter: `Q / (A * D^0.5)` where A = full cross-sectional area of the barrel.

**Unsubmerged** (Q/(A*D^0.5) <= 3.5), Form 1:

`HW/D = Hc/D + K * (Q/(A*D^0.5))^M + slope_sign * S`

where Hc is the specific head at critical depth (dc + Vc^2/(2g)).

**Submerged** (Q/(A*D^0.5) >= 4.0):

`HW/D = c * (Q/(A*D^0.5))^2 + Y + slope_sign * S`

**Transition** (3.5 < Q/(A*D^0.5) < 4.0): linearly interpolate between unsubmerged and submerged values.

Regression coefficients (K, M, c, Y) and slope_sign depend on culvert configuration:

| Configuration | K | M | c | Y | slope_sign |
|--------------|------|------|--------|------|------------|
| concrete_square_edge_headwall | 0.0098 | 2.0 | 0.0398 | 0.67 | -0.5 |
| concrete_groove_end_headwall | 0.0078 | 2.0 | 0.0292 | 0.74 | -0.5 |
| concrete_groove_end_projecting | 0.0045 | 2.0 | 0.0317 | 0.69 | -0.5 |
| cmp_headwall | 0.0078 | 2.0 | 0.0379 | 0.69 | -0.5 |
| cmp_mitered | 0.0210 | 1.33 | 0.0463 | 0.75 | +0.7 |
| cmp_projecting | 0.0340 | 1.50 | 0.0553 | 0.54 | -0.5 |

### Outlet Control (HDS-5)

Assuming full-flow conditions through the barrel:

`HW = H + ho - L * S`

where total head loss H = He + Hf + Ho:

- **Entrance loss:** He = ke * V^2/(2g)
- **Friction loss:** Hf = (19.63 * n^2 * L) / R^(4/3) * V^2/(2g)
- **Exit loss:** Ho = 1.0 * V^2/(2g)

For full circular pipe: R = D/4, A = pi*D^2/4.

Outlet depth: ho = max(TW, (dc + D)/2)

where dc is critical depth, found by solving Q^2*T/(g*A^3) = 1 for the circular cross-section.

Entrance loss coefficients (ke) and Manning's n by configuration:

| Configuration | ke | Manning's n |
|--------------|------|-------------|
| concrete_square_edge_headwall | 0.5 | 0.013 |
| concrete_groove_end_headwall | 0.2 | 0.013 |
| concrete_groove_end_projecting | 0.2 | 0.013 |
| cmp_headwall | 0.5 | 0.024 |
| cmp_mitered | 0.7 | 0.024 |
| cmp_projecting | 0.9 | 0.024 |

### Controlling Condition

The controlling condition is whichever produces the higher headwater depth. Report 1.0 for inlet control, 2.0 for outlet control.

### Headwater Elevation

`Headwater elevation = Inlet invert elevation + Controlling headwater depth`

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "inlet_control_hw_m": <numeric_value>,
  "outlet_control_hw_m": <numeric_value>,
  "controlling_condition": <numeric_value>,
  "headwater_elevation_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
