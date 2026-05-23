You are a senior security and electrical systems engineer checking CCTV camera coverage.

## Problem

Calculate the horizontal field of view, pixels per metre, and margin against the target pixel density.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Horizontal resolution | {{ horizontal_pixels }} | px |
| Sensor width | {{ sensor_width_mm }} | mm |
| Lens focal length | {{ lens_focal_length_mm }} | mm |
| Target distance | {{ target_distance_m }} | m |
{% if target_ppm is defined %}
| Target pixel density | {{ target_ppm }} | px/m |
{% endif %}
{% if archetype_description is defined %}

### Site Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A CCTV PPM calculation tool is available at `/workspace/ppm-calculation_calc.py`. Run it with:

```bash
python3 /workspace/ppm-calculation_calc.py --help
```
{% endif %}

## Required

Calculate:

1. Horizontal field of view in m
2. Pixels per metre at the target plane
3. Percentage margin relative to the target pixel density

## Constraints

- Use `horizontal_field_of_view = sensor_width x target_distance / focal_length`.
- Sensor width and focal length are both in mm, so their ratio is dimensionless.
- Use `pixels_per_meter = horizontal_pixels / horizontal_field_of_view`.
- Use `target_ppm_margin_pct = (pixels_per_meter / target_ppm - 1) x 100`.

## Output Format

Show your working in Markdown. At the end, include a JSON block with exactly these keys:

```json
{
  "horizontal_field_of_view_m": <numeric_value>,
  "pixels_per_meter": <numeric_value>,
  "target_ppm_margin_pct": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
