You are a mechanical product reviewer checking a task-owned synthetic SSC-15 product submittal review packet for one pump package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Procore Submittals, Autodesk Construction Cloud Submittals, ICC-ES evaluation reports, UL Product iQ, FM Approvals, and BBA certificate routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Submittal package: `SUB-15-PKG-001`
- Submittal register: `REG-15-SUB-001`
- Pump datasheet: `DAT-15-PUMP-001`
- Pressure certificate: `CERT-15-PRESS-001`
- Duty calculation excerpt: `CALC-15-DUTY-001`
- Review comment log: `CMT-15-REVIEW-001`
- Deviation register: `DEV-15-LOG-001`
- Disposition memo: `MEMO-15-DISP-001`
- Specification section: `SPEC-15-15100`

All checks use the same `SUB-15-PKG-001` product package and `REG-15-SUB-001` register. Do not change the product identity, certificate identity, duty point, review comments, deviation status, or specification basis unless you explicitly flag a source conflict.

Unit convention for this source pack:

- Flow is in L/s.
- Head is in m.
- Motor power is in kW.
- Pressure is in kPa.
- Review periods are calendar days.
- Evidence, certificates, comments, and deviations are counts.

## Duty And Certificate Basis

| Item | Value |
|------|-------|
| Required design flow | {{ required_flow_l_s }} L/s |
| Submitted datasheet flow | {{ submitted_flow_l_s }} L/s |
| Required design head | {{ required_head_m }} m |
| Submitted datasheet head | {{ submitted_head_m }} m |
| Pump BEP flow | {{ bep_flow_l_s }} L/s |
| POR lower bound | {{ por_low_percent }} percent of BEP flow |
| POR upper bound | {{ por_high_percent }} percent of BEP flow |
| Motor nameplate power | {{ motor_nameplate_kw }} kW |
| Motor service factor | {{ motor_service_factor }} |
| Required motor power | {{ required_motor_kw }} kW |
| Maximum system pressure | {{ max_system_pressure_kpa }} kPa |
| Certificate pressure rating | {{ certificate_pressure_rating_kpa }} kPa |

Duty and certificate checks:

- Flow capacity margin equals `submitted_flow_l_s - required_flow_l_s`.
- Flow capacity ratio equals `submitted_flow_l_s / required_flow_l_s`.
- Head capacity margin equals `submitted_head_m - required_head_m`.
- Head capacity ratio equals `submitted_head_m / required_head_m`.
- BEP flow percent equals `required_flow_l_s / bep_flow_l_s x 100`.
- POR minimum flow equals `bep_flow_l_s x por_low_percent / 100`.
- POR maximum flow equals `bep_flow_l_s x por_high_percent / 100`.
- POR low margin equals `required_flow_l_s - por_min_flow_l_s`.
- POR high margin equals `por_max_flow_l_s - required_flow_l_s`.
- Motor available power equals `motor_nameplate_kw x motor_service_factor`.
- Motor margin equals `motor_available_kw - required_motor_kw`.
- Pressure certificate margin equals `certificate_pressure_rating_kpa - max_system_pressure_kpa`.

## Evidence And Review Basis

| Item | Value |
|------|-------|
| Required evidence items | {{ required_evidence_items }} |
| Submitted evidence items | {{ submitted_evidence_items }} |
| Required certificate fields | {{ required_certificate_items }} |
| Matching certificate fields | {{ matching_certificate_items }} |
| Total review comments | {{ total_review_comments }} |
| Closed review comments | {{ closed_review_comments }} |
| Open critical comments | {{ open_critical_comments }} |
| Allowed review period | {{ review_period_days }} days |
| Elapsed review period | {{ elapsed_review_days }} days |
| Approved deviations | {{ approved_deviation_count }} |
| Unresolved deviations | {{ unresolved_deviation_count }} |

Evidence and review checks:

- Evidence completeness percent equals `submitted_evidence_items / required_evidence_items x 100`.
- Certificate match percent equals `matching_certificate_items / required_certificate_items x 100`.
- Review closeout percent equals `closed_review_comments / total_review_comments x 100`.
- Review days remaining equals `review_period_days - elapsed_review_days`.
- Approved deviation count is the source value from `DEV-15-LOG-001`.
- Unresolved deviation count is the source value from `DEV-15-LOG-001`.
- Open critical comments is the source value from `CMT-15-REVIEW-001`.
- Overall pass score is `1.0` only when flow, head, POR low/high margins, motor margin, pressure certificate margin, evidence completeness, certificate match, review closeout, review days remaining, open critical comments, and unresolved deviations all pass; otherwise it is `0.0`.

## Output Format

Write a compact submittal disposition memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "flow_capacity_margin_l_s": <numeric_value>,
  "flow_capacity_ratio": <numeric_value>,
  "head_capacity_margin_m": <numeric_value>,
  "head_capacity_ratio": <numeric_value>,
  "bep_flow_percent": <numeric_value>,
  "por_min_flow_l_s": <numeric_value>,
  "por_max_flow_l_s": <numeric_value>,
  "por_low_margin_l_s": <numeric_value>,
  "por_high_margin_l_s": <numeric_value>,
  "motor_available_kw": <numeric_value>,
  "motor_margin_kw": <numeric_value>,
  "pressure_certificate_margin_kpa": <numeric_value>,
  "evidence_completeness_percent": <numeric_value>,
  "certificate_match_percent": <numeric_value>,
  "review_closeout_percent": <numeric_value>,
  "review_days_remaining": <numeric_value>,
  "approved_deviation_count": <numeric_value>,
  "unresolved_deviation_count": <numeric_value>,
  "open_critical_comments": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
