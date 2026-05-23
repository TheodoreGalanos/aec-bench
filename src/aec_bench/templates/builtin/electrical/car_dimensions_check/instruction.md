# ABOUTME: Prompt template for lift car dimension margin tasks.
# ABOUTME: Presents actual and minimum car dimensions plus rated load.

You are a senior vertical transportation engineer checking lift car dimension margins.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Car internal width | {{ car_internal_width_mm }} | mm |
| Car internal depth | {{ car_internal_depth_mm }} | mm |
| Door clear opening | {{ door_clear_opening_mm }} | mm |
| Rated load | {{ rated_load_kg }} | kg |
| Minimum internal width | {{ minimum_width_mm }} | mm |
| Minimum internal depth | {{ minimum_depth_mm }} | mm |
| Minimum door opening | {{ minimum_door_opening_mm }} | mm |

## Constraints

- Width margin equals actual car width minus minimum width.
- Depth margin equals actual car depth minus minimum depth.
- Door opening margin equals actual clear opening minus minimum clear opening.
- Car floor area equals internal width times internal depth, converted from mm2 to m2.
- Rated load density equals rated load divided by car floor area.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "width_margin_mm": <numeric_value>,
  "depth_margin_mm": <numeric_value>,
  "door_opening_margin_mm": <numeric_value>,
  "car_floor_area_m2": <numeric_value>,
  "rated_load_density_kg_m2": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
