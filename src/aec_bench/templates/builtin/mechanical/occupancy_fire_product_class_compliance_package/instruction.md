You are a code-compliance reviewer checking a task-owned synthetic SSC-15 occupancy/fire/product-class compliance note.

Use only the task-owned synthetic source pack values shown below for numeric grading. Listing directories, fire product classes, and authority routes shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-15-LH-07`
- Occupancy schedule: `OCC-15-SCHED-07`
- Product datasheet: `DAT-15-PRODUCT-07`
- Fire/hazard class note: `FIRE-15-CLASS-07`
- Authority reference: `AUTH-15-REF-07`
- Calculation appendix: `CALC-15-APP-07`
- Compliance response memo: `MEMO-15-CODE-07`

All checks use the same occupancy context, product class, and authority reference. Do not change the occupancy schedule, product identity, fire class, or authority criterion unless you explicitly flag a source conflict.

## Source Values

| Item | Value |
|------|-------|
| Floor area | {{ floor_area_m2 }} m2 |
| Occupant area factor | {{ occupant_area_factor_m2_per_person }} m2/person |
| Product class capacity | {{ product_class_capacity_persons }} persons |
| Flame spread index | {{ flame_spread_index }} |
| Flame spread limit | {{ flame_spread_limit }} |
| Smoke developed index | {{ smoke_developed_index }} |
| Smoke developed limit | {{ smoke_developed_limit }} |
| Fire resistance rating | {{ fire_resistance_rating_min }} min |
| Required fire resistance | {{ required_fire_resistance_min }} min |
| NAC devices | {{ nac_device_count }} |
| NAC current per device | {{ nac_current_per_device_a }} A |
| NAC supply capacity | {{ nac_supply_capacity_a }} A |
| Smoke exhaust ACH | {{ smoke_exhaust_ach }} |
| Required smoke exhaust ACH | {{ required_smoke_exhaust_ach }} |
| Authority evidence items | {{ authority_evidence_items }} |
| Required authority evidence items | {{ required_authority_evidence_items }} |

Occupant load equals floor area divided by occupant area factor. NAC current margin equals supply capacity minus device count times current per device.

## Output Format

Write a compact compliance response memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "occupant_load_persons": <numeric_value>,
  "product_class_capacity_margin_persons": <numeric_value>,
  "flame_spread_margin": <numeric_value>,
  "smoke_developed_margin": <numeric_value>,
  "fire_resistance_margin_min": <numeric_value>,
  "nac_current_margin_a": <numeric_value>,
  "smoke_exhaust_ach_margin": <numeric_value>,
  "authority_evidence_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
