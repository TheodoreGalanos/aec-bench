You are a senior structural engineer specializing in bridge composite section design.

## Task

Calculate transformed section properties for the steel-concrete composite girder in {{ site_context }}.

## Given

| Parameter | Value | Unit |
| --- | ---: | --- |
| Top flange width | {{ top_flange_width_mm }} | mm |
| Top flange thickness | {{ top_flange_thickness_mm }} | mm |
| Web depth between flanges | {{ web_depth_mm }} | mm |
| Web thickness | {{ web_thickness_mm }} | mm |
| Bottom flange width | {{ bottom_flange_width_mm }} | mm |
| Bottom flange thickness | {{ bottom_flange_thickness_mm }} | mm |
| Effective slab width | {{ slab_width_mm }} | mm |
| Slab thickness | {{ slab_thickness_mm }} | mm |
| Haunch width | {{ haunch_width_mm }} | mm |
| Haunch thickness | {{ haunch_thickness_mm }} | mm |
| Modular ratio | {{ modular_ratio }} | - |

## Constraints

- No internet access is available.
- Use transformed-section analysis with concrete area and inertia divided by the modular ratio.
- Measure vertical dimensions from the bottom of the bottom flange.
- Model the steel section as three rectangles: bottom flange, web, and top flange.
- Model the concrete as two transformed rectangles: haunch and slab.
- Use the parallel-axis theorem to calculate transformed second moment of area.

{% if tool_available %}
## Available Tool

A calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate:

- Transformed composite section area (`transformed_area_mm2`)
- Neutral axis from bottom of steel section (`neutral_axis_from_bottom_mm`)
- Transformed second moment of area (`transformed_inertia_mm4`)
- Bottom section modulus (`bottom_section_modulus_mm3`)
- Top section modulus (`top_section_modulus_mm3`)

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "transformed_area_mm2": <numeric_value>,
  "neutral_axis_from_bottom_mm": <numeric_value>,
  "transformed_inertia_mm4": <numeric_value>,
  "bottom_section_modulus_mm3": <numeric_value>,
  "top_section_modulus_mm3": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
