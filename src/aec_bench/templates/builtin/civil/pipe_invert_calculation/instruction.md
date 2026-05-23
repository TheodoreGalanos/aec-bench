You are a senior civil engineer specializing in stormwater drainage design in Australia.

## Problem

Calculate the downstream invert level, obvert (crown) level, cover depth, and grade fall for a stormwater drainage pipe. Determine whether the cover depth at the downstream end meets the minimum requirement for the installation context.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Upstream invert level (IL_us) | {{ upstream_invert_m }} | m AHD |
| Pipe length (L) | {{ pipe_length_m }} | m |
| Pipe grade | {{ pipe_grade_percent }} | % |
| Pipe diameter (D) | {{ pipe_diameter_mm }} | mm |
| Surface level at downstream pit | {{ surface_level_ds_m }} | m AHD |
{%- if minimum_cover_mm is defined %}
| Minimum cover requirement | {{ minimum_cover_mm }} | mm |
{%- endif %}
{%- if archetype_description is defined %}

### Installation Context

{{ archetype_description }}
{% endif %}

{% if tool_available %}
## Available Tool

A pipe invert calculation tool is available at `/workspace/pipe-invert-calculation_calc.py`. Run it with:

```bash
python3 /workspace/pipe-invert-calculation_calc.py --help
```

You may use this tool to verify your calculations or compute values directly.
{% endif %}

## Required

Calculate the following:

1. Grade fall over the pipe length (m)
2. Downstream invert level IL_ds (m AHD)
3. Obvert (crown) level at the downstream end OL_ds (m AHD)
4. Cover depth at the downstream end (mm)
5. Cover adequacy (1.0 if cover >= minimum requirement, 0.0 if insufficient)

## Applicable Standards

- AS/NZS 3500.3 — Stormwater drainage
- QUDM Section 7 — Pipe drainage design

## Minimum Cover Requirements (Typical Australian Practice)

| Installation Context | Minimum Cover (mm) |
|---------------------|-------------------|
| Under road pavement | 600 |
| Under verge or footpath | 450 |
| Under heavy traffic / trunk mains | 600–900 |

## Constraints

- No internet access is available. Work from engineering knowledge and the provided tool.
- Use the following formulae:
  - **Grade fall:** fall = (grade / 100) × L
  - **Downstream invert:** IL_ds = IL_us − fall
  - **Obvert (crown) level:** OL_ds = IL_ds + D, where D is the diameter in metres (convert from mm)
  - **Cover depth:** cover_mm = (surface_level_ds − OL_ds) × 1000
  - **Cover adequacy:** 1.0 if cover_mm ≥ minimum_cover_mm, otherwise 0.0
- Round all numerical outputs to 2 decimal places.

## Output Format

Show your step-by-step working in Markdown, including unit conversions, grade fall, invert calculation, obvert calculation, cover depth, and adequacy check. At the end of your solution, include a JSON block with your final answers in exactly this format:

```json
{
  "downstream_invert_m": <numeric_value>,
  "obvert_level_m": <numeric_value>,
  "cover_depth_mm": <numeric_value>,
  "grade_fall_m": <numeric_value>,
  "cover_adequate": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
