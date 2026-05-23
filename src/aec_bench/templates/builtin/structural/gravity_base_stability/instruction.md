You are a senior structural engineer specializing in gravity base foundation checks.

## Problem

Calculate reduced gravity base stability from vertical load, overturning moment, base geometry, and allowable bearing pressure.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Vertical load | {{ vertical_load_kn }} | kN |
| Overturning moment | {{ overturning_moment_knm }} | kNm |
| Base width in overturning direction | {{ base_width_m }} | m |
| Base length | {{ base_length_m }} | m |
| Allowable bearing pressure | {{ allowable_bearing_kpa }} | kPa |

{% if archetype_description is defined %}
### Foundation Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A gravity base stability calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Load eccentricity
2. Middle-third eccentricity limit
3. Maximum bearing pressure
4. Bearing utilisation ratio
5. Numeric middle-third flag, where 1 means the eccentricity is within the middle third

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use eccentricity = overturning moment / vertical load.
- Use middle-third limit = base width / 6.
- Use maximum bearing = average bearing x (1 + 6e / base width).

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "eccentricity_m": <numeric_value>,
  "middle_third_limit_m": <numeric_value>,
  "maximum_bearing_kpa": <numeric_value>,
  "bearing_utilisation_ratio": <numeric_value>,
  "middle_third_satisfied": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.

