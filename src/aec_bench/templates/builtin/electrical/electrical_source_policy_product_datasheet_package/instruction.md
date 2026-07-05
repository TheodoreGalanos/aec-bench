You are an electrical design engineer checking `SSC-05-LH-08`, a task-owned synthetic SSC-05 electrical source-policy and product datasheet package.

Use only the task-owned synthetic source pack values below for numeric grading. Datasheet review, certificate/listing, rating-table, worksheet, and submittal-register workflows shape the context only; this instance does not parse a real datasheet, certificate, product listing, or calculation workbook.

## Scene

- Design case: `CASE-SSC05-DATASHEET-08`
- Product datasheet: `DATA-05-PRODUCT-08`
- Certificate/listing record: `CERT-05-LISTING-08`
- Rating table: `RATING-05-TABLE-08`
- Calculation worksheet: `CALC-05-WORKSHEET-08`
- Submittal register: `SUBMIT-05-REGISTER-08`
- Submittal response: `RESPONSE-05-SUBMITTAL-08`

## Source Values

| Item | Value |
|------|-------|
| Provided datasheet fields | {{ provided_datasheet_fields }} |
| Required datasheet fields | {{ required_datasheet_fields }} |
| Traced source values | {{ traced_source_values }} |
| Required source values | {{ required_source_values }} |
| Product nameplate current | {{ product_nameplate_current_a }} A |
| Product derating factor | {{ product_derating_factor }} |
| Design current | {{ design_current_a }} A |
| Cable allowable current | {{ cable_allowable_current_a }} A |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |
| Calculated voltage drop | {{ calculated_voltage_drop_percent }} % |
| Protection-setting margin | {{ protection_setting_margin_percent }} % |
| Review comments | {{ review_comment_count }} |
| Resolved comments | {{ resolved_comment_count }} |
| Critical open comments | {{ critical_open_comments }} |
| Response completeness score | {{ response_completeness_score }} |

Checks:

- Datasheet completeness equals provided fields divided by required fields.
- Source trace score equals traced source values divided by required source values.
- Derated product current equals nameplate current times the derating factor.
- Breaker and cable margins compare derated or allowable current against design current.
- Open comments equal review comments minus resolved comments.
- Overall pass score is `1.0` only when source, rating, setting, response, and critical-comment checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated datasheet extraction evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "datasheet_completeness_fraction": <numeric_value>,
  "source_trace_score": <numeric_value>,
  "derated_product_current_a": <numeric_value>,
  "breaker_rating_margin_a": <numeric_value>,
  "cable_rating_margin_a": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "protection_setting_margin_percent": <numeric_value>,
  "open_comments": <numeric_value>,
  "critical_open_comments": <numeric_value>,
  "response_completeness_score": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
