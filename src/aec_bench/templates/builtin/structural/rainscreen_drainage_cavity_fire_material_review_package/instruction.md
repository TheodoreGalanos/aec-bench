You are a structural/facade engineer checking a task-owned synthetic SSC-09 rainscreen drainage, cavity, fire/material review package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Rainscreen cavity drainage, cladding material-submittal, thermal-break, and fire-stop review workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-09-LH-05`
- Rainscreen detail: `RAINSCREEN-09-DETAIL-05`
- Cavity drainage note: `CAVITY-09-DRAIN-05`
- Material data register: `MAT-09-DATA-05`
- Fire-stop schedule: `FIRESTOP-09-SCHED-05`
- Review comment register: `REVIEW-09-MAT-05`
- Envelope coordination memo: `MEMO-09-ENVELOPE-05`

## Source Values

| Item | Value |
|------|-------|
| Cavity depth | {{ cavity_depth_mm }} mm |
| Minimum cavity depth | {{ minimum_cavity_depth_mm }} mm |
| Open joint area | {{ open_joint_area_cm2_m }} cm2/m |
| Required vent area | {{ required_vent_area_cm2_m }} cm2/m |
| Drainage slot area | {{ drainage_slot_area_cm2 }} cm2 |
| Required drainage slot area | {{ required_drainage_slot_area_cm2 }} cm2 |
| Product documents submitted | {{ product_documents_submitted }} |
| Product documents required | {{ product_documents_required }} |
| Fire-stop spacing | {{ fire_stop_spacing_m }} m |
| Maximum fire-stop spacing | {{ max_fire_stop_spacing_m }} m |
| Thermal break count | {{ thermal_break_count }} |
| Bracket count | {{ bracket_count }} |
| Review comments | {{ review_comments }} |
| Resolved review comments | {{ resolved_review_comments }} |
| Critical open comments | {{ critical_open_comments }} |

## Checks

- Cavity depth margin equals cavity depth minus minimum cavity depth.
- Vent area margin equals open joint area minus required vent area.
- Drainage slot margin equals drainage slot area minus required drainage slot area.
- Material evidence score equals submitted product documents divided by required product documents.
- Fire-stop spacing margin equals maximum spacing minus proposed spacing.
- Thermal break coverage fraction equals thermal break count divided by bracket count.
- Review resolution fraction equals resolved review comments divided by review comments.
- Overall pass score is `1.0` only when drainage/cavity/fire margins are non-negative, material evidence is at least `0.9`, thermal-break coverage is at least `0.95`, all review comments are resolved, and no critical comments remain; otherwise it is `0.0`.

## Output Format

Write a compact rainscreen review memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "cavity_depth_margin_mm": <numeric_value>,
  "vent_area_margin_cm2_m": <numeric_value>,
  "drainage_slot_margin_cm2": <numeric_value>,
  "material_evidence_score": <numeric_value>,
  "fire_stop_spacing_margin_m": <numeric_value>,
  "thermal_break_coverage_fraction": <numeric_value>,
  "review_resolution_fraction": <numeric_value>,
  "critical_open_comments": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
