You are a senior structural engineer specializing in facade wind loading.

## Problem

Calculate effective wind area for pressure coefficient selection from cladding panel dimensions and supporting-member tributary area.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Panel width | {{ panel_width_m }} | m |
| Panel height | {{ panel_height_m }} | m |
| Supporting member span | {{ supporting_member_span_m }} | m |
| Tributary width | {{ tributary_width_m }} | m |
| Minimum effective area | {{ minimum_effective_area_m2 }} | m2 |

{% if archetype_description is defined %}
### Facade Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

An effective wind area calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Cladding panel area (m2)
2. Supporting member tributary area (m2)
3. Effective wind area (m2)
4. Area averaging ratio

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use panel area = panel width x panel height.
- Use member tributary area = supporting member span x tributary width.
- Use effective wind area = max(panel area, member tributary area, minimum effective area).
- Use area averaging ratio = effective wind area / minimum effective area.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "panel_area_m2": <numeric_value>,
  "member_tributary_area_m2": <numeric_value>,
  "effective_wind_area_m2": <numeric_value>,
  "area_averaging_ratio": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
