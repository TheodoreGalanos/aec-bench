You are an electrical/life-safety engineer checking a task-owned synthetic SSC-08 emergency power for life-safety and vertical movement package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External emergency-power, generator, battery-bridge, lift/escalator, feeder, and load-shedding workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-08-LH-03`
- Emergency operations plan: `EMERG-08-PLAN-03`
- Lift schedule: `LIFT-08-SCHED-03`
- Escalator schedule: `ESC-08-SCHED-03`
- Fire alarm load schedule: `ALARM-08-LOAD-03`
- Backup power sheet: `BACKUP-08-POWER-03`
- Emergency power memo: `MEMO-08-POWER-03`

## Source Values

| Item | Value |
|------|-------|
| Critical lift load | {{ critical_lift_load_kw }} kW |
| Escalator recovery load | {{ escalator_recovery_load_kw }} kW |
| Alarm load | {{ alarm_load_kw }} kW |
| Smoke control load | {{ smoke_control_load_kw }} kW |
| Emergency lighting load | {{ emergency_lighting_load_kw }} kW |
| Diversity factor | {{ diversity_factor }} |
| Generator capacity | {{ generator_capacity_kw }} kW |
| Generator derate factor | {{ generator_derate_factor }} |
| Control load | {{ control_load_kw }} kW |
| Bridge duration | {{ bridge_duration_h }} h |
| Battery usable fraction | {{ battery_usable_fraction }} |
| Selected battery capacity | {{ selected_battery_capacity_kwh }} kWh |
| Voltage | {{ voltage_v }} V |
| Power factor | {{ power_factor }} |
| Feeder length | {{ feeder_length_km }} km |
| Feeder resistance | {{ feeder_resistance_ohm_per_km }} ohm/km |
| Feeder reactance | {{ feeder_reactance_ohm_per_km }} ohm/km |
| Allowable voltage drop | {{ allowable_voltage_drop_percent }} percent |
| Shedable load | {{ shedable_load_kw }} kW |
| Required shed | {{ required_shed_kw }} kW |

## Checks

- Critical connected load equals the sum of critical lift, escalator recovery, alarm, smoke control, and emergency lighting loads.
- Diversified emergency load equals connected load times diversity factor.
- Available generator capacity equals generator capacity times derate factor.
- Generator capacity margin equals available generator capacity minus diversified emergency load.
- Battery bridge load equals alarm load plus emergency lighting load plus control load.
- Required battery capacity equals bridge load times bridge duration divided by usable fraction.
- Emergency feeder current uses three-phase power, voltage, and power factor.
- Feeder voltage drop uses feeder R/X, length, current, and power factor.
- Load-shed margin equals shedable load minus required shed.
- Overall pass score is `1.0` only when generator, battery, voltage-drop, and load-shed margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact emergency power memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "critical_connected_load_kw": <numeric_value>,
  "diversified_emergency_load_kw": <numeric_value>,
  "available_generator_capacity_kw": <numeric_value>,
  "generator_capacity_margin_kw": <numeric_value>,
  "battery_bridge_load_kw": <numeric_value>,
  "required_battery_capacity_kwh": <numeric_value>,
  "battery_capacity_margin_kwh": <numeric_value>,
  "emergency_feeder_current_a": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "load_shed_margin_kw": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
