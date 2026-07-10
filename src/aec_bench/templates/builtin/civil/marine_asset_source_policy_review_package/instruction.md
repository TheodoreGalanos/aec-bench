You are a civil/marine reviewer checking a task-owned synthetic SSC-04 marine asset source-policy and review packet.

Use only the task-owned synthetic source pack values shown below for numeric grading. External datum, criteria, asset-register, calculation-appendix, comment-register, and authority-boundary workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-04-LH-08`
- Datum statement: `DATUM-04-STATEMENT-08`
- Criteria matrix: `CRITERIA-04-MATRIX-08`
- Marine asset schedule: `ASSET-04-MARINE-08`
- Calculation appendix: `CALC-04-APPENDIX-08`
- Comment register: `COMMENT-04-REGISTER-08`
- Source-policy memo: `MEMO-04-SOURCE-08`

## Source Values

| Item | Value |
|------|-------|
| Datum items traced | {{ datum_items_traced }} |
| Required datum items | {{ required_datum_items }} |
| Resolved criteria items | {{ resolved_criteria_items }} |
| Criteria items | {{ criteria_items }} |
| Matching asset rows | {{ matching_asset_rows }} |
| Asset schedule rows | {{ asset_schedule_rows }} |
| Traced calculation rows | {{ traced_calculation_rows }} |
| Calculation rows | {{ calculation_rows }} |
| Resolved comments | {{ resolved_comments }} |
| Review comments | {{ review_comments }} |
| Separated authority roles | {{ separated_authority_roles }} |
| Required authority roles | {{ required_authority_roles }} |
| Unsupported source value count | {{ unsupported_source_value_count }} |
| Response sections | {{ response_sections }} |
| Required response sections | {{ required_response_sections }} |

## Checks

- Datum trace score equals datum items traced divided by required datum items.
- Criteria resolution fraction equals resolved criteria items divided by criteria items.
- Asset schedule match fraction equals matching asset rows divided by asset schedule rows.
- Calculation trace fraction equals traced calculation rows divided by calculation rows.
- Comment resolution fraction equals resolved comments divided by review comments.
- Authority partition score equals separated authority roles divided by required authority roles.
- Response completeness score equals response sections divided by required response sections.
- Evidence boundary score is the average of datum trace, criteria resolution, asset match, calculation trace, comment resolution, authority partition, and response completeness scores.
- Overall pass score is `1.0` only when datum, criteria, and authority partition checks are complete, unsupported source values are zero, and response completeness is at least 0.9; otherwise it is `0.0`.

## Output Format

Write a compact source-policy review memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "datum_trace_score": <numeric_value>,
  "criteria_resolution_fraction": <numeric_value>,
  "asset_schedule_match_fraction": <numeric_value>,
  "calculation_trace_fraction": <numeric_value>,
  "comment_resolution_fraction": <numeric_value>,
  "authority_partition_score": <numeric_value>,
  "unsupported_source_value_count": <numeric_value>,
  "response_completeness_score": <numeric_value>,
  "evidence_boundary_score": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
