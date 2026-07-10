You are checking a task-owned synthetic SSC-12 construction noise and vibration monitoring package.

Use only the source pack values below for numeric grading. Construction noise/vibration monitoring practice and FTA-style screening workflows provide context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-12-LH-04`
- Construction staging plan: `STAGE-12-CONST-04`
- Equipment/source schedule: `EQUIP-12-SOURCE-04`
- Receiver map: `RCV-12-MAP-04`
- Monitoring criterion: `MON-12-CRIT-04`
- Complaint/action log: `LOG-12-ACTION-04`
- Construction impact memo: `MEMO-12-CONST-04`

Compute receiver construction noise, combined construction noise, noise action margin, vibration transmissibility, receiver vibration velocity, vibration action margin, monitoring data headroom, complaint response margin, and pass score.

Write `/workspace/output.md` with a compact memo preserving the object IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "receiver_construction_noise_dba": <numeric_value>,
  "combined_construction_noise_dba": <numeric_value>,
  "noise_action_margin_db": <numeric_value>,
  "vibration_transmissibility": <numeric_value>,
  "receiver_vibration_velocity_mm_s": <numeric_value>,
  "vibration_action_margin_mm_s": <numeric_value>,
  "monitoring_data_headroom_mb": <numeric_value>,
  "complaint_response_margin_h": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
