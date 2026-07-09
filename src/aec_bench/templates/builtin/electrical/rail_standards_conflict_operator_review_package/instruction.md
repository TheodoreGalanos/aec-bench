You are a rail operator-review engineer checking `SSC-02-LH-08`, a task-owned synthetic SSC-02 rail standards conflict and operator review package.

Use only the task-owned synthetic source pack values below for numeric grading. Rail standards matrices and authority review workflows shape the context only; this instance does not validate a real operator standard, accepted review, or authority approval.

## Scene

- Design case: `CASE-SSC02-STANDARDS-08`
- Standards matrix: `STD-02-MATRIX-08`
- Comment register: `COMMENT-02-REGISTER-08`
- Alignment and signal source pack: `ALIGN-02-SIGNAL-08`
- Calculation extracts: `CALC-02-EXTRACT-08`
- Exception approval route: `EXCEPT-02-APPROVAL-08`
- Authority-partitioned response: `RESPONSE-02-AUTH-08`

## Source Values

| Item | Value |
|------|-------|
| Candidate standards | {{ candidate_standards_count }} |
| Selected standards | {{ selected_standards_count }} |
| Conflicting comments | {{ conflicting_comments }} |
| Resolved comments | {{ resolved_comments }} |
| Affected calculations | {{ affected_calculations }} |
| Calculations updated | {{ calculations_updated }} |
| Exception requests | {{ exception_requests }} |
| Approved exceptions | {{ approved_exceptions }} |
| Source values traced | {{ source_values_traced }} |
| Required source values | {{ required_source_values }} |
| Response sections | {{ response_sections }} |
| Required response sections | {{ required_response_sections }} |
| Critical open comments | {{ critical_open_comments }} |

Checks:

- Standard selection fraction equals selected standards divided by candidate standards.
- Comment resolution fraction equals resolved comments divided by conflicting comments.
- Calculation update fraction equals updated calculations divided by affected calculations.
- Exception resolution fraction equals approved exceptions divided by exception requests.
- Source trace and response completeness are source-owned fractions.
- Overall pass score is `1.0` only when the review completeness thresholds pass and no critical comments remain; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, operator-standard validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "standard_selection_fraction": <numeric_value>,
  "comment_resolution_fraction": <numeric_value>,
  "calculation_update_fraction": <numeric_value>,
  "exception_resolution_fraction": <numeric_value>,
  "source_trace_score": <numeric_value>,
  "response_completeness_score": <numeric_value>,
  "operator_review_score": <numeric_value>,
  "open_comments": <numeric_value>,
  "critical_open_comments": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
