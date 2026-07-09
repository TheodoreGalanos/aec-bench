You are a product compliance reviewer checking a task-owned synthetic SSC-15 certificate conflict and repair portfolio.

Use only the task-owned synthetic source pack values shown below for numeric grading. Substitution, certificate, and review workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-15-LH-08`
- Conflicting datasheet A: `DAT-15-A-08`
- Replacement datasheet B: `DAT-15-B-08`
- Certificate record: `CERT-15-REC-08`
- Source index: `INDEX-15-SRC-08`
- Calculation trace: `TRACE-15-CALC-08`
- Repair response memo: `RESPONSE-15-REPAIR-08`

All checks use the same source index, certificate record, affected calculations, and repair memo. Do not change the selected authority source, replacement product, capacity value, or conflict status unless you explicitly flag a source conflict.

## Source Values

| Item | Value |
|------|-------|
| Selected source is current | {{ selected_source_is_current }} |
| Selected source has authority | {{ selected_source_has_authority }} |
| Affected calculations | {{ affected_calculation_count }} |
| Updated calculations | {{ updated_calculation_count }} |
| Governing certificate capacity | {{ governing_certificate_capacity_kn }} kN |
| Conflicting datasheet capacity | {{ conflicting_datasheet_capacity_kn }} kN |
| Replacement capacity | {{ replacement_capacity_kn }} kN |
| Required capacity | {{ required_capacity_kn }} kN |
| Total conflict items | {{ total_conflict_items }} |
| Closed conflict items | {{ closed_conflict_items }} |
| Unresolved conflicts | {{ unresolved_conflict_count }} |
| Expired sources still used | {{ expired_source_count }} |
| Completed repair memo sections | {{ completed_repair_memo_sections }} |
| Required repair memo sections | {{ required_repair_memo_sections }} |

Source authority score is the lower of the current-source and authority-source indicators.

## Output Format

Write a compact repair memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "source_authority_score": <numeric_value>,
  "affected_calculation_update_fraction": <numeric_value>,
  "certificate_capacity_delta_kn": <numeric_value>,
  "replacement_capacity_margin_kn": <numeric_value>,
  "source_conflict_closure_fraction": <numeric_value>,
  "unresolved_conflict_count": <numeric_value>,
  "expired_source_count": <numeric_value>,
  "repair_memo_completeness_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
