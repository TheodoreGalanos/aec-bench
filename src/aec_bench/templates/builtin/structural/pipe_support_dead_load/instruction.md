You are a senior structural engineer specializing in pipe support dead-load checks.

## Problem

Calculate the operating and hydrotest dead line loads for a supported pipe from geometry, densities, and insulation thickness.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Pipe outside diameter | {{ pipe_outer_diameter_mm }} | mm |
| Pipe wall thickness | {{ pipe_wall_thickness_mm }} | mm |
| Steel density | {{ steel_density_kg_m3 }} | kg/m3 |
| Contents density | {{ contents_density_kg_m3 }} | kg/m3 |
| Insulation thickness | {{ insulation_thickness_mm }} | mm |
| Insulation density | {{ insulation_density_kg_m3 }} | kg/m3 |
| Hydrotest density | {{ hydrotest_density_kg_m3 }} | kg/m3 |

{% if archetype_description is defined %}
### Structural Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A pipe support dead-load calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Steel pipe load from the steel annulus area, steel density, and gravity
2. Contents load from the pipe internal area, contents density, and gravity
3. Insulation load from the insulation annulus area, insulation density, and gravity
4. Operating line load as steel pipe load plus contents load plus insulation load
5. Hydrotest line load as steel pipe load plus hydrotest contents load plus insulation load

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use 9.81 m/s2 for gravity.
- Convert millimetre diameters and thicknesses to metres before calculating areas.
- Do not add clamps, shoes, valves, corrosion allowance, or other support loads.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "steel_pipe_load_kn_m": <numeric_value>,
  "contents_load_kn_m": <numeric_value>,
  "insulation_load_kn_m": <numeric_value>,
  "operating_line_load_kn_m": <numeric_value>,
  "hydrotest_line_load_kn_m": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
