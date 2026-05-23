You are a senior structural engineer specializing in marine berthing structures.

## Problem

Calculate vessel berthing energy using the kinetic energy method and the supplied berthing coefficients.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Vessel displacement | {{ vessel_displacement_t }} | t |
| Approach velocity | {{ approach_velocity_m_s }} | m/s |
| Added mass coefficient CM | {{ added_mass_coefficient }} | - |
| Eccentricity coefficient CE | {{ eccentricity_coefficient }} | - |
| Berth configuration coefficient CC | {{ berth_configuration_coefficient }} | - |
| Softness coefficient CS | {{ softness_coefficient }} | - |
| Safety factor | {{ safety_factor }} | - |

{% if archetype_description is defined %}
### Berthing Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A berthing energy calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Unmodified vessel kinetic energy (kNm)
2. Characteristic berthing energy (kNm)
3. Design berthing energy (kNm)
4. Product of berthing coefficients

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Convert vessel displacement from tonnes to kg by multiplying by 1000.
- Use kinetic energy = 0.5 x mass x velocity^2 / 1000 to obtain kNm.
- Use characteristic energy = kinetic energy x CM x CE x CC x CS.
- Use design energy = characteristic energy x safety factor.

## Output Format

Show your step-by-step working in Markdown. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "kinetic_energy_knm": <numeric_value>,
  "characteristic_energy_knm": <numeric_value>,
  "design_energy_knm": <numeric_value>,
  "coefficient_product": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
