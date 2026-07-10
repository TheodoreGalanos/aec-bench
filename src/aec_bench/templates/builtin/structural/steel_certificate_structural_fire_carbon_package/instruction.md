You are a structural material reviewer checking a task-owned synthetic SSC-15 steel certificate package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Product compliance directories and certificate workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-15-LH-01`
- Mill certificate: `CERT-15-STEEL-01`
- Material schedule: `MAT-15-SCHED-01`
- Welding criterion: `WELD-15-CRIT-01`
- Fire design note: `FIRE-15-NOTE-01`
- Structural calculation excerpt: `CALC-15-STRUCT-01`
- Material compliance memo: `MEMO-15-STEEL-01`

All checks use the same steel certificate and material schedule. Do not change the product identity, certificate identity, material grade, fire basis, or memo status unless you explicitly flag a source conflict.

## Source Values

| Item | Value |
|------|-------|
| Carbon | {{ carbon_percent }} percent |
| Manganese | {{ manganese_percent }} percent |
| Chromium | {{ chromium_percent }} percent |
| Molybdenum | {{ molybdenum_percent }} percent |
| Vanadium | {{ vanadium_percent }} percent |
| Nickel | {{ nickel_percent }} percent |
| Copper | {{ copper_percent }} percent |
| Carbon-equivalent limit | {{ carbon_equivalent_limit }} |
| Certificate capacity | {{ certificate_capacity_kn }} kN |
| Design load | {{ design_load_kn }} kN |
| Fire load ratio | {{ fire_load_ratio }} |
| Required fire temperature | {{ required_fire_temperature_c }} degC |
| Matching certificate fields | {{ matching_certificate_fields }} |
| Required certificate fields | {{ required_certificate_fields }} |
| Completed memo sections | {{ completed_memo_sections }} |
| Required memo sections | {{ required_memo_sections }} |

Carbon equivalent equals `C + Mn/6 + (Cr + Mo + V)/5 + (Ni + Cu)/15`. Critical steel temperature equals `905 - 690 x fire_load_ratio`.

## Output Format

Write a compact material compliance memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "carbon_equivalent": <numeric_value>,
  "carbon_equivalent_margin": <numeric_value>,
  "structural_capacity_margin_kn": <numeric_value>,
  "structural_utilization": <numeric_value>,
  "critical_steel_temperature_c": <numeric_value>,
  "fire_temperature_margin_c": <numeric_value>,
  "certificate_field_match_fraction": <numeric_value>,
  "material_memo_completeness_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
