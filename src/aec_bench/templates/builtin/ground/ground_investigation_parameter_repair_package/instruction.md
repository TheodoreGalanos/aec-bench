You are checking a task-owned synthetic SSC-07 ground investigation review and parameter repair package for `SSC-07-LH-08`.

Use only the task-owned synthetic source pack values shown below for numeric grading.

## Source Pack

- Ground investigation review: `GIR-07-REVIEW-01`
- CPT repair source: `CPT-07-REPAIR-01`
- Lab/test repair source: `LAB-07-REPAIR-01`
- Affected calculation excerpts: `CALC-07-AFFECTED-01`
- Geotechnical review response: `MEMO-07-REPAIR-01`

## Source Values

| Item | Value |
|---|---:|
| CPT-derived phi | {{ cpt_phi_deg }} degrees |
| Lab-test phi | {{ lab_phi_deg }} degrees |
| Adopted repaired phi | {{ adopted_phi_deg }} degrees |
| SPT N1,60 | {{ spt_n1_60 }} |
| Minimum N1,60 | {{ minimum_n1_60 }} |
| Applied bearing pressure | {{ applied_bearing_pressure_kpa }} kPa |
| Repaired allowable bearing | {{ repaired_allowable_bearing_kpa }} kPa |
| Wall sliding FS | {{ wall_sliding_fs }} |
| Minimum wall sliding FS | {{ minimum_wall_sliding_fs }} |
| Repaired grid resistance | {{ repaired_grid_resistance_ohm }} ohm |
| Maximum grid resistance | {{ maximum_grid_resistance_ohm }} ohm |
| Closed comments | {{ closed_comments }} |
| Total comments | {{ total_comments }} |

Compute the phi source delta, adopted phi, SPT margin, bearing utilization and margin, wall sliding margin, grid resistance margin, comment closeout, and overall pass score.

Write a compact source-bound geotechnical review response to `/workspace/output.md`. Preserve the source IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "phi_source_delta_deg": <numeric_value>,
  "adopted_phi_deg": <numeric_value>,
  "spt_n1_60_margin": <numeric_value>,
  "bearing_utilization": <numeric_value>,
  "bearing_margin_kpa": <numeric_value>,
  "wall_sliding_fs_margin": <numeric_value>,
  "grid_resistance_margin_ohm": <numeric_value>,
  "comment_closeout_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
