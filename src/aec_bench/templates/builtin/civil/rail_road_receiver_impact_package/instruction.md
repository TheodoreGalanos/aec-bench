You are checking a task-owned synthetic SSC-12 rail or road receiver impact package.

Use only the source pack values below for numeric grading. FHWA TNM, rail/road corridor assessment, and receiver mitigation workflows provide context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-12-LH-05`
- Corridor plan/profile: `CORR-12-PLAN-05`
- Traffic or train scenario: `TRAFFIC-12-SCENARIO-05`
- Receiver plan: `RCV-12-CORR-05`
- Source spectrum: `SPEC-12-CORR-05`
- Mitigation criterion: `MIT-12-BARRIER-05`
- Corridor impact memo: `MEMO-12-CORR-05`

Compute traffic source level, receiver noise level, combined corridor level, corridor noise margin, corridor vibration velocity, corridor vibration margin, mitigation height margin, and pass score.

Write `/workspace/output.md` with a compact memo preserving the object IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "traffic_source_level_dba": <numeric_value>,
  "receiver_noise_level_dba": <numeric_value>,
  "combined_corridor_level_dba": <numeric_value>,
  "corridor_noise_margin_db": <numeric_value>,
  "corridor_vibration_velocity_mm_s": <numeric_value>,
  "corridor_vibration_margin_mm_s": <numeric_value>,
  "mitigation_height_margin_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
