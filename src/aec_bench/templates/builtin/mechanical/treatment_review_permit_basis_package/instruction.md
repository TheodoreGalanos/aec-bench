You are a wastewater process engineer checking a task-owned synthetic SSC-10 treatment review response and permit-basis package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Permit criteria, sampling data, process calculation appendix, comment register, and authority-matrix workflows shape the context only; this instance does not parse a real permit, model branch, or accepted project report.

## Scene

- Product: `SSC-10-LH-08`
- Permit criteria table: `PERMIT-10-CRIT-08`
- Sampling dataset: `SAMPLE-10-DATA-08`
- Process calculation appendix: `CALC-10-APPX-08`
- Comment register: `COMMENT-10-REG-08`
- Authority matrix: `AUTH-10-MATRIX-08`
- Compliance gap memo: `MEMO-10-PERMIT-08`

## Source Values

| Item | Value |
| --- | --- |
| Base required SRT | {{ base_required_srt_d }} d |
| Governing temperature | {{ temperature_c }} deg C |
| Theta factor | {{ theta_factor }} |
| Actual SRT | {{ actual_srt_d }} d |
| Permit BOD | {{ permit_bod_mg_l }} mg/L |
| Predicted BOD | {{ predicted_bod_mg_l }} mg/L |
| Permit ammonia | {{ permit_ammonia_mg_l }} mg/L |
| Predicted ammonia | {{ predicted_ammonia_mg_l }} mg/L |
| Oxygen required | {{ oxygen_required_kg_d }} kg/d |
| Oxygen capacity | {{ oxygen_capacity_kg_d }} kg/d |
| Chemical required | {{ chemical_required_kg_d }} kg/d |
| Chemical capacity | {{ chemical_capacity_kg_d }} kg/d |
| Sludge predicted | {{ sludge_predicted_kg_d }} kg/d |
| Sludge handling capacity | {{ sludge_handling_capacity_kg_d }} kg/d |
| Review comments | {{ total_review_comments }} total |
| Closed comments | {{ closed_review_comments }} |
| Critical comments open | {{ critical_comments_open }} |
| Source references found | {{ source_references_found }} |
| Source references required | {{ source_references_required }} |

## Calculation Rules

- Required SRT equals `base_required_srt_d x theta_factor^(20 - temperature_c)`.
- SRT margin equals actual SRT minus required SRT.
- Permit margins equal permit limits minus predicted values.
- Process capacity margins equal listed capacity minus required or predicted values.
- Comments resolved fraction equals closed review comments divided by total review comments.
- Source completeness fraction equals found source references divided by required references.
- Response completeness score averages comment closure, source completeness, and critical-comment closure.
- Overall pass score is `1.0` only when permit, process capacity, and critical-comment checks pass.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "required_srt_d": <numeric_value>,
  "srt_margin_d": <numeric_value>,
  "bod_permit_margin_mg_l": <numeric_value>,
  "ammonia_permit_margin_mg_l": <numeric_value>,
  "oxygen_capacity_margin_kg_d": <numeric_value>,
  "chemical_capacity_margin_kg_d": <numeric_value>,
  "sludge_capacity_margin_kg_d": <numeric_value>,
  "comments_resolved_fraction": <numeric_value>,
  "source_completeness_fraction": <numeric_value>,
  "response_completeness_score": <numeric_value>,
  "critical_comments_open": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
