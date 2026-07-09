You are an electrical fire-life-safety engineer checking a task-owned synthetic SSC-19 alarm, smoke control, and emergency power package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Fire alarm, smoke control, battery autonomy, and emergency generator workflows shape the context only; this instance does not run external software, parse real panel schedules, or validate a code clause.

## Scene

- Product: `SSC-19-LH-04`
- Alarm zone schedule: `ALARM-19-ZONE-04`
- NAC load schedule: `NAC-19-LOAD-04`
- Smoke ventilation schedule: `SMOKE-19-VENT-04`
- Battery life calculation: `BATT-19-LIFE-04`
- Emergency operation basis: `OPS-19-EMERG-04`
- Life-safety memo: `MEMO-19-LIFE-04`

## Source Values

| Item | Value |
| --- | --- |
| Strobe count | {{ strobe_count }} |
| Strobe current | {{ strobe_current_a }} A |
| Speaker count | {{ speaker_count }} |
| Speaker current | {{ speaker_current_a }} A |
| NAC capacity | {{ nac_capacity_a }} A |
| Smoke fan count | {{ smoke_fan_count }} |
| Smoke fan power | {{ smoke_fan_power_kw }} kW |
| Smoke control load | {{ smoke_control_load_kw }} kW |
| Battery autonomy | {{ battery_autonomy_h }} h |
| Battery DC voltage | {{ battery_dc_voltage_v }} V |
| Usable battery fraction | {{ usable_battery_fraction }} |
| Installed battery capacity | {{ installed_battery_ah }} Ah |
| Generator rating | {{ generator_rating_kw }} kW |
| Starting factor | {{ starting_factor }} |
| Smoke zone volume | {{ smoke_zone_volume_m3 }} m3 |
| Exhaust flow | {{ exhaust_flow_m3_s }} m3/s |
| Required smoke exhaust ACH | {{ required_smoke_exhaust_ach }} ACH |

## Checks

- NAC current equals strobe count times strobe current plus speaker count times speaker current.
- Smoke control load equals fan count times fan power plus control load.
- Battery required amp-hours equals NAC current times autonomy divided by usable battery fraction.
- Generator required kW equals smoke control load times starting factor plus NAC DC load in kW.
- Smoke exhaust ACH equals exhaust flow times 3600 divided by smoke zone volume.
- Overall pass score is `1.0` only when NAC, battery, generator, and smoke exhaust margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated smoke-control model evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "nac_current_a": <numeric_value>,
  "nac_current_margin_a": <numeric_value>,
  "smoke_control_load_kw": <numeric_value>,
  "battery_required_ah": <numeric_value>,
  "battery_capacity_margin_ah": <numeric_value>,
  "generator_required_kw": <numeric_value>,
  "generator_margin_kw": <numeric_value>,
  "smoke_exhaust_ach": <numeric_value>,
  "smoke_exhaust_ach_margin": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
