You are a structural engineer checking a task-owned synthetic SSC-14 structural review packet and authority overlay.

Use only the task-owned synthetic source pack values below for numeric grading. Structural source indices, load schedules, material certificates, review comments, and authority criteria shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-14-LH-08`
- Source index and calculation appendix: `INDEX-SSC14-008`
- Load schedule: `LOAD-SSC14-008`
- Material certificate: `MAT-SSC14-008`
- Review comment register: `COMMENTS-SSC14-008`
- Acceptance/gap response memo: `MEMO-SSC14-008`

## Source Values

- Dead, live, and wind loads: {{ dead_load_kn }} kN, {{ live_load_kn }} kN, {{ wind_load_kn }} kN
- ULS load factors D, L, W and SLS wind factor: {{ uls_dead_factor }}, {{ uls_live_factor }}, {{ uls_wind_factor }}, {{ sls_wind_factor }}
- Member capacity, SLS deflection limit, and calculated SLS deflection: {{ member_capacity_kn }} kN, {{ sls_deflection_limit_mm }} mm, {{ calculated_sls_deflection_mm }} mm
- Material certificate chemistry: C {{ carbon_percent }} %, Mn {{ manganese_percent }} %, Cr {{ chromium_percent }} %, Mo {{ molybdenum_percent }} %, V {{ vanadium_percent }} %, Ni {{ nickel_percent }} %, Cu {{ copper_percent }} %
- Carbon equivalent limit: {{ carbon_equivalent_limit }}
- Evidence items present/required: {{ present_evidence_items }} / {{ required_evidence_items }}
- Review comments closed/total and unresolved critical comments: {{ closed_review_comment_count }} / {{ review_comment_count }}, {{ unresolved_critical_comments }}
- Authority override count and thresholds: {{ authority_override_count }}, {{ minimum_evidence_percent }} %, {{ minimum_comment_closeout_percent }} %

## Required Calculations

- ULS load is `D_factor x D + L_factor x L + W_factor x W`.
- SLS load is `D + L + SLS_wind_factor x W`.
- ULS capacity margin is member capacity minus ULS load.
- SLS deflection margin is limit minus calculated deflection.
- Material carbon equivalent is `C + Mn / 6 + (Cr + Mo + V) / 5 + (Ni + Cu) / 15`.
- Evidence completeness is present evidence divided by required evidence.
- Comment closeout is closed comments divided by total comments.
- Overall pass score is `1.0` only when load margins, material margin, evidence completeness, comment closeout, and unresolved critical comment checks pass.

Write a compact acceptance/gap response memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "governing_uls_load_kn": <numeric_value>,
  "governing_sls_load_kn": <numeric_value>,
  "uls_capacity_margin_kn": <numeric_value>,
  "sls_deflection_margin_mm": <numeric_value>,
  "material_carbon_equivalent": <numeric_value>,
  "carbon_equivalent_margin": <numeric_value>,
  "evidence_complete_percent": <numeric_value>,
  "comment_closeout_percent": <numeric_value>,
  "unresolved_critical_comments": <numeric_value>,
  "authority_override_count": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
