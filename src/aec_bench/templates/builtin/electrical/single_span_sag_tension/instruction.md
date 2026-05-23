You are a senior electrical engineer specializing in overhead contact line design for rail electrification.

## Problem

Calculate the mid-span sag (parabolic and exact catenary), wire length, and catenary constant for a single level span of overhead contact wire per EN 50119.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Span length (L) | {{ span_length_m }} | m |
{% if wire_weight_per_m_n is defined %}
| Wire weight per unit length (w) | {{ wire_weight_per_m_n }} | N/m |
{% endif %}
| Horizontal tension (T) | {{ horizontal_tension_n }} | N |
| Wire diameter | {{ wire_diameter_mm }} | mm |
{% if archetype_description is defined %}

### Installation Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A sag-tension calculation tool is available at `/workspace/single-span-sag-tension_calc.py`. Run it with:

```bash
python3 /workspace/single-span-sag-tension_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Mid-span sag using the parabolic approximation (m)
2. Mid-span sag using the exact catenary equation (m)
3. Total wire length in the span using the catenary equation (m)
4. Catenary constant C (m)

## Applicable Standards

- EN 50119 — Railway applications — Fixed installations — Electric traction overhead contact lines
- EN 50367 — Railway applications — Current collection systems — Technical criteria for the interaction between pantograph and overhead contact line

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following equations:
  - Catenary constant: C = T / w, where T is horizontal tension (N) and w is weight per unit length (N/m)
  - Parabolic sag: S = w * L^2 / (8 * T), where L is span length (m)
  - Exact catenary sag: S_cat = C * (cosh(L / (2 * C)) - 1)
  - Wire length (catenary): l = 2 * C * sinh(L / (2 * C))
- The parabolic approximation is valid when sag is less than about 5% of span length. The exact catenary gives the precise result regardless of sag-to-span ratio.
- cosh and sinh are hyperbolic cosine and sine functions respectively.

## Output Format

Show your step-by-step working in Markdown, including the catenary constant calculation, both sag methods, and the wire length computation. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "sag_m": <numeric_value>,
  "sag_catenary_m": <numeric_value>,
  "wire_length_m": <numeric_value>,
  "catenary_constant_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
