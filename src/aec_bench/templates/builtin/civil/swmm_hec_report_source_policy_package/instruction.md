You are a civil stormwater modeller checking a task-owned synthetic SSC-03 SWMM/HEC-style report output and source-policy package.

Use only the task-owned synthetic source pack values shown below for numeric grading. EPA SWMM report workflows, HEC-style model report review, source manifest hashing, and negative-case verification shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-03-LH-08`
- Model input file: `MODEL-SSC03-008`
- Manual/report PDF: `REPORT-SSC03-008`
- Result table: `RESULT-SSC03-008`
- Hash/source manifest: `HASH-SSC03-008`
- Verification case matrix: `VERIFY-SSC03-008`
- Source-policy memo: `MEMO-SSC03-008`

## Source Values

| Item | Value |
|------|-------|
| Model subcatchments | {{ model_subcatchment_count }} |
| Report subcatchments | {{ report_subcatchment_count }} |
| Model nodes | {{ model_node_count }} |
| Report nodes | {{ report_node_count }} |
| Model links | {{ model_link_count }} |
| Report links | {{ report_link_count }} |
| Storage units | {{ storage_unit_count }} |
| Outlet result rows | {{ outlet_row_count }} |
| Required hashes | {{ required_hash_count }} |
| Present hashes | {{ present_hash_count }} |
| Manual peak flow | {{ manual_peak_flow_m3_s }} m3/s |
| Model peak flow | {{ model_peak_flow_m3_s }} m3/s |
| Allowed peak delta | {{ allowed_peak_delta_m3_s }} m3/s |
| Continuity error | {{ continuity_error_percent }} percent |
| Maximum continuity error | {{ maximum_continuity_error_percent }} percent |
| Expected negative cases | {{ expected_negative_cases }} |
| Captured negative cases | {{ captured_negative_cases }} |
| Unresolved source conflicts | {{ unresolved_source_conflicts }} |

## Checks

- Object match percent compares model and report subcatchment, node, and link counts.
- Hash completeness percent equals present hashes divided by required hashes.
- Peak delta equals absolute manual/model peak-flow difference.
- Overall pass score is `1.0` only when object, hash, peak-delta, continuity, negative-case, and source-conflict checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated SWMM report-output evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "object_match_percent": <numeric_value>,
  "hash_completeness_percent": <numeric_value>,
  "peak_delta_m3_s": <numeric_value>,
  "peak_delta_margin_m3_s": <numeric_value>,
  "continuity_error_percent": <numeric_value>,
  "continuity_margin_percent": <numeric_value>,
  "storage_unit_count": <numeric_value>,
  "outlet_row_count": <numeric_value>,
  "negative_case_capture_percent": <numeric_value>,
  "unresolved_source_conflicts": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
