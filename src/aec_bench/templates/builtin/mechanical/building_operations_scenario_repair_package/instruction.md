You are a building services reviewer checking a task-owned synthetic SSC-08 building operations review and scenario repair package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External room/floor plan, occupancy change, system-schedule, criteria-matrix, review-comment, and repair-ledger workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-08-LH-08`
- Room/floor plan: `PLAN-08-FLOOR-08`
- Occupancy source table: `OCC-08-SOURCE-08`
- System schedules: `SYSTEM-08-SCHED-08`
- Criteria matrix: `CRIT-08-MATRIX-08`
- Comment register: `COMMENT-08-REG-08`
- Operations repair memo: `MEMO-08-REPAIR-08`

## Source Values

| Item | Value |
|------|-------|
| Source items traced | {{ source_items_traced }} |
| Required source items | {{ required_source_items }} |
| Occupancy rows updated | {{ occupancy_rows_updated }} |
| Required occupancy rows | {{ required_occupancy_rows }} |
| Affected system checks complete | {{ affected_system_checks_complete }} |
| Required system checks | {{ required_system_checks }} |
| Resolved comments | {{ resolved_comments }} |
| Review comments | {{ review_comments }} |
| Open critical comment count | {{ open_critical_comment_count }} |
| Partitioned authority roles | {{ partitioned_authority_roles }} |
| Required authority roles | {{ required_authority_roles }} |
| Repair actions closed | {{ repair_actions_closed }} |
| Required repair actions | {{ required_repair_actions }} |
| Unsupported value count | {{ unsupported_value_count }} |

## Checks

- Source trace score equals source items traced divided by required source items.
- Occupancy update fraction equals updated occupancy rows divided by required occupancy rows.
- Affected system check fraction equals completed affected system checks divided by required system checks.
- Comment resolution fraction equals resolved comments divided by review comments.
- Authority partition score equals partitioned authority roles divided by required authority roles.
- Repair action closure fraction equals repair actions closed divided by required repair actions.
- Evidence boundary score is the average of source trace, occupancy update, affected-system, comment, authority, and repair fractions.
- Overall pass score is `1.0` only when source trace, occupancy update, authority, comment, affected-system, critical-comment, and unsupported-value checks pass; otherwise it is `0.0`.

## Output Format

Write a compact operations response memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "source_trace_score": <numeric_value>,
  "occupancy_update_fraction": <numeric_value>,
  "affected_system_check_fraction": <numeric_value>,
  "comment_resolution_fraction": <numeric_value>,
  "open_critical_comment_count": <numeric_value>,
  "authority_partition_score": <numeric_value>,
  "repair_action_closure_fraction": <numeric_value>,
  "unsupported_value_count": <numeric_value>,
  "evidence_boundary_score": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
