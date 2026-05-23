You are a senior civil/dams engineer specializing in dam stability and seepage analysis.

## Problem

Calculate the uplift pressure distribution on a concrete gravity dam foundation and determine the total uplift force per unit length of dam.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Headwater depth (H_u) | {{ headwater_depth_m }} | m |
| Tailwater depth (H_d) | {{ tailwater_depth_m }} | m |
| Base width (B) | {{ base_width_m }} | m |
| Drain distance from upstream face (d_drain) | {{ drain_distance_m }} | m |
{% if drain_efficiency_pct is defined %}
| Drain efficiency (eta) | {{ drain_efficiency_pct }} | % |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An uplift pressure calculation tool is available at `/workspace/uplift-pressure_calc.py`. Run it with:

```bash
python3 /workspace/uplift-pressure_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Uplift pressure at the upstream face P_upstream (kPa)
2. Uplift pressure at the drain line P_drain (kPa)
3. Uplift pressure at the downstream face P_downstream (kPa)
4. Total uplift force per unit length of dam U (kN/m)

## Applicable Standards

- USACE EM 1110-2-2200 — Gravity Dam Design
- USBR Design Standard No. 13 — Embankment Dams

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the simplified bilinear uplift pressure distribution per USACE EM 1110-2-2200:
  - **P_upstream = gamma_w * H_u** (full headwater pressure at the upstream face)
  - **P_drain = gamma_w * (H_d + (1 - eta) * (H_u - H_d))** (reduced pressure at the drain line)
  - **P_downstream = gamma_w * H_d** (full tailwater pressure at the downstream face)
  - Where eta = drain efficiency (0 to 1), H_u = headwater depth, H_d = tailwater depth
- Total uplift force per unit length (trapezoidal integration):
  - **U = 0.5 * (P_upstream + P_drain) * d_drain + 0.5 * (P_drain + P_downstream) * (B - d_drain)**
  - Where d_drain = distance from upstream face to drain line, B = total base width
- Use gamma_w = 9.81 kN/m3
- USACE recommends drain efficiency of 0.25 to 0.50 for preliminary design; up to 0.67 for well-maintained galleries
- If drain efficiency is not given, estimate based on structure type: small weirs 25-50%, gravity dams with galleries 40-67%

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "upstream_pressure_kpa": <numeric_value>,
  "drain_pressure_kpa": <numeric_value>,
  "downstream_pressure_kpa": <numeric_value>,
  "total_uplift_force_kn_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
