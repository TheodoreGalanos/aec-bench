You are a fire protection reviewer checking a task-owned synthetic SSC-19 fire review response and evidence-boundary package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Fire review response, source-index checking, authority-role separation, and evidence-conflict workflows shape the context only; this instance does not validate a real authority decision, accepted project evidence, or source-pack parser.

## Scene

- Product: `SSC-19-LH-08`
- Source index: `SOURCE-19-INDEX-08`
- Review comment register: `COMMENT-19-REVIEW-08`
- Hazard table: `HAZ-19-TABLE-08`
- Calculation extract: `CALC-19-EXTRACT-08`
- Authority source matrix: `AUTH-19-SOURCE-08`
- Response memo: `RESPONSE-19-MEMO-08`

## Source Values

| Item | Value |
| --- | --- |
| Source items traced | {{ source_items_traced }} |
| Required source items | {{ required_source_items }} |
| Review comments | {{ review_comments }} |
| Resolved comments | {{ resolved_comments }} |
| Affected checks | {{ affected_checks }} |
| Updated checks | {{ updated_checks }} |
| Unresolved gaps | {{ unresolved_gaps }} |
| Allowed gaps | {{ allowed_gaps }} |
| Authority roles | {{ authority_roles }} |
| Separated authority roles | {{ separated_authority_roles }} |
| Evidence conflicts | {{ evidence_conflicts }} |
| Resolved conflicts | {{ resolved_conflicts }} |
| Critical open comments | {{ critical_open_comments }} |
| Response sections | {{ response_sections }} |
| Required response sections | {{ required_response_sections }} |

## Checks

- Source trace score equals traced source items divided by required source items.
- Comment resolution fraction equals resolved comments divided by review comments.
- Affected check update fraction equals updated checks divided by affected checks.
- Allowed gap margin equals allowed gaps minus unresolved gaps.
- Authority role separation score equals separated roles divided by authority roles.
- Conflict resolution fraction equals resolved conflicts divided by evidence conflicts.
- Response completeness score equals response sections divided by required response sections.
- Review boundary score averages source, comment, check, authority-role, conflict, and response scores.
- Overall pass score is `1.0` only when gap margin, check updates, role separation, and critical-comment checks pass; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "source_trace_score": <numeric_value>,
  "comment_resolution_fraction": <numeric_value>,
  "affected_check_update_fraction": <numeric_value>,
  "unresolved_gap_count": <numeric_value>,
  "allowed_gap_margin": <numeric_value>,
  "authority_role_separation_score": <numeric_value>,
  "conflict_resolution_fraction": <numeric_value>,
  "response_completeness_score": <numeric_value>,
  "review_boundary_score": <numeric_value>,
  "critical_open_comments": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
