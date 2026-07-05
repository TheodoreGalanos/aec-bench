You are an equipment review engineer checking a task-owned synthetic SSC-06 equipment datasheet and commissioning review package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Datasheet review, POR/AOR screening, commissioning, and review-comment workflows shape the context only; this instance does not run external software or parse a real source pack.

## Scene

- Product: `SSC-06-LH-08`
- Equipment schedule: `EQUIP-06-SCHED-08`
- Manufacturer datasheet: `DATASHEET-06-MFR-08`
- Curve/table export: `CURVE-06-EXPORT-08`
- Commissioning checklist: `COMM-06-CHECK-08`
- Review comments: `REVIEW-06-COMMENTS-08`
- Review response: `MEMO-06-REVIEW-08`

## Source Values

| Item | Value |
| --- | --- |
| Scheduled duty flow | {{ scheduled_flow_l_s }} L/s |
| Datasheet max flow | {{ datasheet_max_flow_l_s }} L/s |
| Scheduled duty head | {{ scheduled_head_m }} m |
| Datasheet max head | {{ datasheet_max_head_m }} m |
| BEP flow | {{ bep_flow_l_s }} L/s |
| POR lower bound | {{ por_lower_pct }} % of BEP |
| POR upper bound | {{ por_upper_pct }} % of BEP |
| NPSH available | {{ npsh_available_m }} m |
| NPSH required | {{ npsh_required_m }} m |
| Shaft power | {{ shaft_power_kw }} kW |
| Selected motor size | {{ selected_motor_kw }} kW |
| Motor service factor | {{ motor_service_factor }} |
| Provided evidence count | {{ provided_evidence_count }} |
| Required evidence count | {{ required_evidence_count }} |
| Open commissioning items | {{ open_commissioning_items }} |
| Critical review comments open | {{ critical_review_comments_open }} |

## Calculation Rules

- Flow capacity margin percent equals `(datasheet max flow - scheduled flow) / scheduled flow x 100`.
- Head capacity margin percent equals `(datasheet max head - scheduled head) / scheduled head x 100`.
- POR position percent equals scheduled flow divided by BEP flow times 100.
- POR margin percent equals the smaller margin to the lower and upper POR bounds.
- NPSH margin equals NPSH available minus NPSH required.
- Motor service margin equals selected motor size minus shaft power times motor service factor.
- Evidence completeness score equals provided evidence count divided by required evidence count.
- Overall pass score is `1.0` only when capacity, POR, NPSH, motor, evidence completeness, and critical-comment checks pass.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "flow_capacity_margin_pct": <numeric_value>,
  "head_capacity_margin_pct": <numeric_value>,
  "por_position_pct": <numeric_value>,
  "por_margin_pct": <numeric_value>,
  "npsh_margin_m": <numeric_value>,
  "motor_service_margin_kw": <numeric_value>,
  "evidence_completeness_score": <numeric_value>,
  "open_commissioning_items": <numeric_value>,
  "critical_review_comments_open": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
