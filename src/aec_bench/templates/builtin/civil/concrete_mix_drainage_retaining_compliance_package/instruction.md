You are a civil materials reviewer checking a task-owned synthetic SSC-15 concrete or mix compliance package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Product certificate and mix-design workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-15-LH-03`
- Mix design sheet: `MIX-15-DESIGN-03`
- SCM product data: `SCM-15-PRODUCT-03`
- Strength criterion: `STRENGTH-15-CRIT-03`
- Foundation/retaining detail: `FOUND-15-DETAIL-03`
- Exposure class note: `EXP-15-NOTE-03`
- Mix compliance memo: `MEMO-15-MIX-03`

All checks use the same mix design, product selection, and use-case boundary. Do not change the mix identity, SCM record, foundation demand, or exposure basis unless you explicitly flag a source conflict.

## Source Values

| Item | Value |
|------|-------|
| Specified strength | {{ specified_strength_mpa }} MPa |
| Submitted mean strength | {{ submitted_mean_strength_mpa }} MPa |
| Standard deviation | {{ standard_deviation_mpa }} MPa |
| Target strength factor | {{ target_strength_factor }} |
| SCM replacement | {{ scm_replacement_percent }} percent |
| Maximum SCM replacement | {{ max_scm_replacement_percent }} percent |
| Bearing capacity | {{ bearing_capacity_kpa }} kPa |
| Bearing demand | {{ bearing_demand_kpa }} kPa |
| Exposure cover provided | {{ exposure_cover_provided_mm }} mm |
| Exposure cover required | {{ exposure_cover_required_mm }} mm |
| Drainage freeboard provided | {{ drainage_freeboard_provided_m }} m |
| Drainage freeboard required | {{ drainage_freeboard_required_m }} m |
| Matching evidence items | {{ matching_evidence_items }} |
| Required evidence items | {{ required_evidence_items }} |

Target mean strength equals specified strength plus target factor times standard deviation.

## Output Format

Write a compact mix compliance memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "target_mean_strength_mpa": <numeric_value>,
  "strength_margin_mpa": <numeric_value>,
  "scm_replacement_margin_percent": <numeric_value>,
  "bearing_capacity_margin_kpa": <numeric_value>,
  "bearing_utilization": <numeric_value>,
  "exposure_cover_margin_mm": <numeric_value>,
  "drainage_freeboard_margin_m": <numeric_value>,
  "mix_evidence_match_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
