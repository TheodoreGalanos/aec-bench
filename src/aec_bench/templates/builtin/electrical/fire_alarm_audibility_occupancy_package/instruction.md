You are checking a task-owned synthetic SSC-12 fire alarm audibility and occupancy package.

Use only the source pack values below for numeric grading. Fire alarm audibility, room finish, NAC load, and life-safety review workflows provide context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-12-LH-06`
- Floor plan: `FLOOR-12-PLAN-06`
- NAC device schedule: `NAC-12-SCHED-06`
- Room finish schedule: `FINISH-12-ROOM-06`
- Fire alarm load table: `LOAD-12-ALARM-06`
- Life-safety criterion: `CRIT-12-LIFE-06`
- Audibility memo: `MEMO-12-AUD-06`

Compute RT60, audibility level, audibility margin, NAC current, NAC headroom, alarm battery required, alarm battery margin, and pass score.

Write `/workspace/output.md` with a compact memo preserving the object IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "room_rt60_s": <numeric_value>,
  "rt60_margin_s": <numeric_value>,
  "farthest_nac_level_dba": <numeric_value>,
  "combined_alarm_level_dba": <numeric_value>,
  "audibility_margin_db": <numeric_value>,
  "nac_current_a": <numeric_value>,
  "nac_headroom_a": <numeric_value>,
  "alarm_battery_required_kwh": <numeric_value>,
  "alarm_battery_margin_kwh": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
