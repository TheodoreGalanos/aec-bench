You are a senior mechanical engineer specializing in building services acoustics.

## Problem

Calculate the sound pressure level at a target distance from a point source using inverse-square distance attenuation.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Reference SPL L1 | {{ reference_spl_db }} | dB |
| Reference distance r1 | {{ reference_distance_m }} | m |
| Target distance r2 | {{ target_distance_m }} | m |

{% if archetype_description is defined %}
### Acoustic Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A distance attenuation calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Distance ratio r2/r1
2. Geometric spreading attenuation (dB)
3. Sound pressure level at the target distance (dB)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Treat the source as a point source in free-field conditions.
- Use attenuation = 20 log10(r2/r1).
- Use L2 = L1 - attenuation.
- Do not add ground absorption, barrier, meteorological, facade, or directivity corrections.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "distance_ratio": <numeric_value>,
  "attenuation_db": <numeric_value>,
  "target_spl_db": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
