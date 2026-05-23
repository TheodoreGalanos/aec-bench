You are a senior civil engineer specializing in hazardous materials storage and spill containment design.

## Problem

Calculate the required containment bund volume for an oil storage installation in accordance with AS/NZS 1940 (*The storage and handling of flammable and combustible liquids*).

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Number of containers | {{ num_containers }} | - |
| Largest single container volume | {{ largest_container_volume_l }} | L |
| Total stored volume (all containers) | {{ total_stored_volume_l }} | L |
| Bund internal length | {{ bund_length_m }} | m |
| Bund internal width | {{ bund_width_m }} | m |
{% if bund_wall_height_m is defined %}
| Bund wall height | {{ bund_wall_height_m }} | m |
{% endif %}
{% if num_equipment_items is defined and num_equipment_items|int > 0 %}
| Number of equipment items in bund | {{ num_equipment_items }} | - |
| Average equipment footprint area | {{ equipment_footprint_area_m2 }} | m² |
{% endif %}
{% if archetype_description is defined %}

### Site Conditions

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A bund volume calculation tool is available at `/workspace/{{ meta.name }}_calc.py`. Run it with:

```bash
python3 /workspace/{{ meta.name }}_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Required bund capacity per AS/NZS 1940 (m³)
2. Net available bund volume after equipment displacement (m³)
3. Bund wall height (m)
4. Compliance status (1.0 if net volume meets requirement, 0.0 if not)

## Applicable Standards

- AS/NZS 1940:2017 — The storage and handling of flammable and combustible liquids

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the AS/NZS 1940 bund volume method:
  - **Required bund capacity** is the greater of:
    - 110% of the volume of the largest single container
    - 25% of the total stored volume of all containers
  - Convert all volumes from litres to cubic metres (1 m³ = 1000 L)
  - **Gross bund volume:** V_gross = length × width × wall_height
  - **Equipment displacement:** V_equip = num_equipment_items × footprint_area × wall_height
    - Each equipment item is simplified as a rectangular prism extending to the full bund wall height
  - **Net bund volume:** V_net = V_gross − V_equip
  - **Compliance:** V_net ≥ required bund capacity
- Bund wall height must be between 0.15 m and 1.5 m per AS/NZS 1940 practical limits
- If bund wall height is not given directly, select a suitable height based on the installation type and standard practice

## Output Format

Show your step-by-step working in Markdown, including formulas and intermediate calculations. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "required_bund_volume_m3": <numeric_value>,
  "net_bund_volume_m3": <numeric_value>,
  "bund_wall_height_m": <numeric_value>,
  "compliance": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
