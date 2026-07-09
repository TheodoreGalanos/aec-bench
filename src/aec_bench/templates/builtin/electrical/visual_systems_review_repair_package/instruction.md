You are an electrical visual systems reviewer checking a task-owned synthetic SSC-13 review and repair package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External review-management, lighting, CCTV, ITS, and network tools shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-13-LH-08`
- Review comments: `REVIEW-13-COMMENTS-08`
- Revised layout: `LAYOUT-13-REV-08`
- Revised device schedule: `DEVICE-13-SCHED-08`
- Calculation trace: `CALC-13-TRACE-08`
- Criteria matrix: `CRIT-13-MATRIX-08`
- Repair response: `RESPONSE-13-REPAIR-08`

All checks use the same comment register, revised layout, device schedule, affected calculation trace, criteria matrix, and response ledger.

## Source Values

| Item | Value |
|------|-------|
| Closed review comments | {{ closed_review_comments }} of {{ total_review_comments }} |
| Updated affected checks | {{ updated_affected_checks }} of {{ required_affected_checks }} |
| Revised minimum lighting | {{ revised_minimum_lux }} lux |
| Required minimum lighting | {{ required_minimum_lux }} lux |
| CCTV pixels and revised target width | {{ cctv_horizontal_pixels }} px / {{ revised_target_width_m }} m |
| Required PPM | {{ required_ppm }} |
| Revised network load and capacity | {{ revised_network_load_mbps }} Mbps / {{ network_capacity_mbps }} Mbps |
| Revised PoE load and budget | {{ revised_poe_load_w }} W / {{ poe_budget_w }} W |
| Unresolved conflicts | {{ unresolved_conflict_count }} |
| Repair memo sections | {{ completed_repair_memo_sections }} of {{ required_repair_memo_sections }} |

## Output Format

Write a compact visual systems review response to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "review_comment_closure_fraction": <numeric_value>,
  "affected_check_update_fraction": <numeric_value>,
  "lighting_minimum_margin_lux": <numeric_value>,
  "revised_cctv_pixels_per_m": <numeric_value>,
  "cctv_ppm_margin": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "poe_headroom_w": <numeric_value>,
  "unresolved_conflict_count": <numeric_value>,
  "repair_memo_completeness_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
