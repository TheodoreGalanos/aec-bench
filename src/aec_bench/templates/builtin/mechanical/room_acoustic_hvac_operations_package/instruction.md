You are checking a task-owned synthetic SSC-12 room acoustic and HVAC operations package.

Use only the source pack values below for numeric grading. Room acoustic, HVAC noise, SoundPLAN/CadnaA room schedules, and spreadsheet workflows provide context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-12-LH-03`
- Room plan/volume: `ROOM-12-PLAN-03`
- Finish schedule: `FINISH-12-SCHED-03`
- HVAC/equipment schedule: `HVAC-12-SCHED-03`
- Occupancy scenario: `OCC-12-SCENARIO-03`
- Acoustic criterion: `CRIT-12-ROOM-03`
- Room acoustic memo: `MEMO-12-ROOM-03`

Compute Sabine RT60, RT60 margin, air changes, two receiver source levels, combined room level, room noise margin, design occupants, and pass score.

Write `/workspace/output.md` with a compact memo preserving the object IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "room_rt60_s": <numeric_value>,
  "rt60_margin_s": <numeric_value>,
  "air_changes_per_h": <numeric_value>,
  "hvac_source_a_level_dba": <numeric_value>,
  "equipment_source_a_level_dba": <numeric_value>,
  "combined_room_level_dba": <numeric_value>,
  "room_noise_margin_db": <numeric_value>,
  "design_occupants": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
