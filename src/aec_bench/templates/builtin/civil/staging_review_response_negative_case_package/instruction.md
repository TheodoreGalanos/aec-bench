You are a construction staging reviewer checking a task-owned synthetic SSC-16 package for review closeout, affected calculation updates, stage-source identity, and repair-ledger completeness.

Use only the task-owned synthetic source pack values shown below for numeric grading. External review, hold-point, inspection, and staging workflows shape the context only; they are not extra data sources for this instance.

## Source Objects

- Product: `SSC-16-LH-08`
- Review comments: `REVIEW-16-COMMENTS-08`
- Revised staging plan: `STAGE-16-REV-08`
- Control schedule: `CONTROL-16-SCHED-08`
- Device inventory: `DEVICE-16-INV-08`
- Criteria matrix: `CRIT-16-MATRIX-08`
- Repair response memo: `RESPONSE-16-REPAIR-08`

## Source Values

| Item | Value |
|------|-------|
| Closed review comments | {{ closed_review_comments }} |
| Total review comments | {{ total_review_comments }} |
| Updated affected checks | {{ updated_affected_checks }} |
| Total affected checks | {{ total_affected_checks }} |
| Matching stage sources | {{ matching_stage_sources }} |
| Referenced stage sources | {{ referenced_stage_sources }} |
| Revised basin capacity | {{ revised_basin_capacity_m3 }} m3 |
| Required basin capacity | {{ required_basin_capacity_m3 }} m3 |
| Scheduled traffic devices | {{ scheduled_traffic_device_count }} |
| Inventoried traffic devices | {{ inventoried_traffic_device_count }} |
| Available temporary power | {{ available_temp_power_w }} W |
| Revised temporary load | {{ revised_temp_load_w }} W |
| Allowed tolerance | {{ allowed_tolerance_mm }} mm |
| Observed tolerance | {{ observed_tolerance_mm }} mm |
| Unresolved conflicts | {{ unresolved_conflict_count }} |
| Completed repair-ledger fields | {{ completed_repair_fields }} |
| Required repair-ledger fields | {{ required_repair_fields }} |

## Required Checks

- Review comments and affected calculations must be fully closed or updated.
- Stage source matching confirms the response uses the same source objects as the revised stage.
- Environmental, traffic, power, and tolerance margins must remain non-negative after repair.
- The repair ledger must have no unresolved conflicts and at least 0.9 completeness.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack, preserve the source object IDs above, and state whether the baseline checks pass.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "review_comment_closure_fraction": <numeric_value>,
  "affected_check_update_fraction": <numeric_value>,
  "stage_source_match_fraction": <numeric_value>,
  "sediment_basin_margin_m3": <numeric_value>,
  "traffic_device_delta_count": <numeric_value>,
  "power_headroom_w": <numeric_value>,
  "tolerance_margin_mm": <numeric_value>,
  "unresolved_conflict_count": <numeric_value>,
  "repair_ledger_completeness_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
