# ABOUTME: Prompt template for road lighting uniformity check tasks.
# ABOUTME: Presents luminance values and target uniformity for calculation.

You are a senior road lighting engineer verifying lighting uniformity.

## Given

| Parameter | Value | Unit |
|-----------|-------|------|
| Minimum luminance | {{ minimum_luminance_cd_m2 }} | cd/m2 |
| Average luminance | {{ average_luminance_cd_m2 }} | cd/m2 |
| Longitudinal minimum luminance | {{ longitudinal_min_luminance_cd_m2 }} | cd/m2 |
| Longitudinal maximum luminance | {{ longitudinal_max_luminance_cd_m2 }} | cd/m2 |
| Target overall uniformity | {{ target_overall_uniformity }} | - |

## Constraints

- Overall uniformity Uo equals minimum luminance divided by average luminance.
- Longitudinal uniformity Ul equals longitudinal minimum luminance divided by longitudinal maximum luminance.
- Overall uniformity margin is the percentage difference from the target overall uniformity.

## Output Format

Include a JSON block with exactly these keys:

```json
{
  "overall_uniformity_uo": <numeric_value>,
  "longitudinal_uniformity_ul": <numeric_value>,
  "overall_uniformity_margin_pct": <numeric_value>
}
```

Write your complete solution to `/workspace/output.md`.
