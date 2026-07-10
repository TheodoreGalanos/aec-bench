You are a structural/facade engineer checking a task-owned synthetic SSC-09 facade submittal review and source-policy package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Facade submittal review, source traceability, calculator checking, material schedule matching, and response-to-comments workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-09-LH-08`
- Source index: `SOURCE-09-INDEX-08`
- Redrawn facade elevation: `ELEV-09-REDRAWN-08`
- Calculation report: `CALC-09-REPORT-08`
- Material schedule: `MAT-09-SCHEDULE-08`
- Review comment register: `COMMENT-09-REVIEW-08`
- Submittal response: `RESPONSE-09-SUBMITTAL-08`

## Source Values

| Item | Value |
|------|-------|
| Source items traced | {{ source_items_traced }} |
| Required source items | {{ required_source_items }} |
| Calculator rows checked | {{ calculator_rows_checked }} |
| Required calculator rows | {{ required_calculator_rows }} |
| Matching material items | {{ matching_material_items }} |
| Material schedule items | {{ material_schedule_items }} |
| Passing utilization rows | {{ passing_utilization_rows }} |
| Utilization rows | {{ utilization_rows }} |
| Resolved comments | {{ resolved_comments }} |
| Review comments | {{ review_comments }} |
| Approved boundary exceptions | {{ approved_boundary_exceptions }} |
| Boundary exceptions | {{ boundary_exceptions }} |
| Unapproved substitution count | {{ unapproved_substitution_count }} |
| Response sections | {{ response_sections }} |
| Required response sections | {{ required_response_sections }} |

## Checks

- Source trace score equals source items traced divided by required source items.
- Calculator check fraction equals calculator rows checked divided by required calculator rows.
- Material match fraction equals matching material items divided by material schedule items.
- Utilization pass fraction equals passing utilization rows divided by utilization rows.
- Comment resolution fraction equals resolved comments divided by review comments.
- Boundary exception resolution fraction equals approved boundary exceptions divided by boundary exceptions.
- Response completeness score equals response sections divided by required response sections.
- Evidence boundary score is the average of source trace, calculator, material, utilization, comment, boundary exception, and response completeness fractions.
- Overall pass score is `1.0` only when calculator checks, utilization rows, and boundary exceptions are fully complete, with zero unapproved substitutions; otherwise it is `0.0`.

## Output Format

Write a compact facade submittal review memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "source_trace_score": <numeric_value>,
  "calculator_check_fraction": <numeric_value>,
  "material_match_fraction": <numeric_value>,
  "utilization_pass_fraction": <numeric_value>,
  "comment_resolution_fraction": <numeric_value>,
  "boundary_exception_resolution_fraction": <numeric_value>,
  "unapproved_substitution_count": <numeric_value>,
  "response_completeness_score": <numeric_value>,
  "evidence_boundary_score": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
