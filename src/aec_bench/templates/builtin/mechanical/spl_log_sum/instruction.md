You are a senior mechanical engineer specializing in building services acoustics.

## Problem

Calculate the combined sound pressure level from three independent sound sources using logarithmic addition.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Source 1 SPL | {{ source_1_spl_db }} | dB |
| Source 2 SPL | {{ source_2_spl_db }} | dB |
| Source 3 SPL | {{ source_3_spl_db }} | dB |

{% if archetype_description is defined %}
### Acoustic Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An SPL logarithmic summation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Sum of linear acoustic energy terms
2. Combined sound pressure level (dB)
3. Dominant individual source level (dB)

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Convert each source level to a linear energy term using 10^(L/10).
- Sum the three linear energy terms.
- Convert back to dB using L_total = 10 log10(sum of linear terms).
- Identify the dominant source as the highest individual SPL.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "total_linear_energy": <numeric_value>,
  "combined_spl_db": <numeric_value>,
  "dominant_source_spl_db": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
