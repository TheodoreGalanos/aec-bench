You are a structural facade reviewer checking a task-owned synthetic SSC-15 facade/fixing certificate package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Facade product certificates and fixing design services shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-15-LH-06`
- Product certificate: `CERT-15-FIX-06`
- Capacity table: `CAP-15-TABLE-06`
- Facade elevation: `ELEV-15-FACADE-06`
- Wind/bracket calculation: `WIND-15-CALC-06`
- Material schedule: `MAT-15-FACADE-06`
- Submittal memo: `MEMO-15-FIX-06`

All checks use the same fixing product, elevation zone, bracket capacity table, and material schedule. Do not change the product identity, elevation zone, capacity table, or material basis unless you explicitly flag a source conflict.

## Source Values

| Item | Value |
|------|-------|
| Wind pressure | {{ wind_pressure_kpa }} kPa |
| Tributary area | {{ tributary_area_m2 }} m2 |
| Load factor | {{ load_factor }} |
| Bracket capacity | {{ bracket_capacity_kn }} kN |
| Anchor shear capacity | {{ anchor_shear_capacity_kn }} kN |
| Anchor shear demand | {{ anchor_shear_demand_kn }} kN |
| Matching certificate fields | {{ matching_certificate_fields }} |
| Required certificate fields | {{ required_certificate_fields }} |
| Material carbon equivalent | {{ carbon_equivalent }} |
| Carbon-equivalent limit | {{ carbon_equivalent_limit }} |
| Adjustment allowance | {{ adjustment_allowance_mm }} mm |
| Measured substrate deviation | {{ measured_deviation_mm }} mm |

Design bracket load equals wind pressure times tributary area times load factor.

## Output Format

Write a compact fixing compliance memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "design_bracket_load_kn": <numeric_value>,
  "bracket_capacity_margin_kn": <numeric_value>,
  "bracket_utilization": <numeric_value>,
  "anchor_shear_margin_kn": <numeric_value>,
  "certificate_field_match_fraction": <numeric_value>,
  "carbon_equivalent_margin": <numeric_value>,
  "tolerance_adjustment_margin_mm": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
