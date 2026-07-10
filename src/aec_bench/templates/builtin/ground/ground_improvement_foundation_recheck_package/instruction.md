You are checking a task-owned synthetic SSC-07 ground improvement acceptance and foundation recheck package for `SSC-07-LH-06`.

Use only the task-owned synthetic source pack values shown below for numeric grading.

## Source Pack

- Ground improvement certificate: `GI-07-CERT-01`
- Post-improvement SPT log: `SPT-07-POST-01`
- Foundation recheck plan: `FDN-07-RECHECK-01`
- Bearing and settlement worksheet: `SETTLE-07-RECHECK-01`
- Foundation review memo: `MEMO-07-FOUND-01`

## Source Values

| Item | Value |
|---|---:|
| Pre-improvement N1,60 | {{ pre_improvement_n1_60 }} |
| Post-improvement N1,60 | {{ post_improvement_n1_60 }} |
| Target N1,60 | {{ target_n1_60 }} |
| Applied bearing pressure | {{ applied_bearing_pressure_kpa }} kPa |
| Bearing factor per blow | {{ bearing_factor_per_blow_kpa }} kPa |
| Footing width | {{ footing_width_m }} m |
| Elastic modulus | {{ elastic_modulus_kpa }} kPa |
| Poisson ratio | {{ poisson_ratio }} |
| Primary settlement | {{ primary_settlement_mm }} mm |
| Allowable settlement | {{ allowable_settlement_mm }} mm |
| Required certificate items | {{ required_certificate_items }} |
| Matching certificate items | {{ matching_certificate_items }} |

Compute improvement ratio, post-improvement N margin, allowable bearing, bearing utilization and margin, immediate settlement, total settlement, settlement margin, certificate match percent, and overall pass score.

Write a compact source-bound foundation review memo to `/workspace/output.md`. Preserve the source IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "improvement_ratio": <numeric_value>,
  "post_improvement_n_margin": <numeric_value>,
  "allowable_bearing_capacity_kpa": <numeric_value>,
  "bearing_utilization": <numeric_value>,
  "bearing_margin_kpa": <numeric_value>,
  "immediate_settlement_mm": <numeric_value>,
  "primary_settlement_mm": <numeric_value>,
  "total_settlement_mm": <numeric_value>,
  "settlement_margin_mm": <numeric_value>,
  "certificate_match_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
