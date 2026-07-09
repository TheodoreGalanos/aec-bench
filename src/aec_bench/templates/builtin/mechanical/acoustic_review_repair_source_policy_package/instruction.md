You are checking a task-owned synthetic SSC-12 acoustic review repair and source-policy package.

Use only the source pack values below for numeric grading. Acoustic review, source-index, comment-register, and criteria-matrix workflows provide context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-12-LH-08`
- Source index: `INDEX-12-SOURCE-08`
- Octave spectra: `SPEC-12-OCTAVE-08`
- Receiver plan: `RCV-12-PLAN-08`
- Comment register: `COMMENT-12-REG-08`
- Criteria matrix: `CRIT-12-MATRIX-08`
- Response memo: `RESPONSE-12-REPAIR-08`

Compute review comment closure, affected calculation updates, source traceability, mitigation delta, corrected noise margin, vibration margin, unresolved conflicts, repair ledger completeness, and pass score.

Write `/workspace/output.md` with a compact memo preserving the object IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "review_comment_closure_fraction": <numeric_value>,
  "affected_calculation_update_fraction": <numeric_value>,
  "source_traceability_fraction": <numeric_value>,
  "mitigation_delta_db": <numeric_value>,
  "corrected_noise_margin_db": <numeric_value>,
  "vibration_margin_mm_s": <numeric_value>,
  "unresolved_conflict_count": <numeric_value>,
  "repair_ledger_completeness_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
