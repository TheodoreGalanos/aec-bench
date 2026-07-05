You are checking a task-owned synthetic SSC-12 equipment enclosure, ventilation, and noise package.

Use only the source pack values below for numeric grading. Equipment enclosure, ventilation, attenuator, and receiver noise workflows provide context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-12-LH-07`
- Enclosure plan/section: `ENC-12-PLAN-07`
- Ventilation schedule: `VENT-12-SCHED-07`
- Equipment spectrum: `SPEC-12-EQUIP-07`
- Receiver plan: `RCV-12-ENC-07`
- Attenuation treatment data: `TREAT-12-ATTEN-07`
- Enclosure design memo: `MEMO-12-ENC-07`

Compute air changes, ventilation margin, receiver enclosure noise, combined receiver level, criterion margin, thermal capacity margin, treatment insertion loss, and pass score.

Write `/workspace/output.md` with a compact memo preserving the object IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "air_changes_per_h": <numeric_value>,
  "ventilation_margin_ach": <numeric_value>,
  "receiver_enclosure_noise_dba": <numeric_value>,
  "combined_receiver_level_dba": <numeric_value>,
  "noise_criterion_margin_db": <numeric_value>,
  "thermal_capacity_margin_kw": <numeric_value>,
  "treatment_insertion_loss_db": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
