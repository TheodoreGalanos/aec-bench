You are a mechanical/vertical-transport engineer checking a task-owned synthetic SSC-08 lift shaft, car dimension, and accessibility service package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External lift planning, shaft/car dimensional review, accessibility service, emergency lift power, and feeder workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-08-LH-06`
- Floor and shaft plan: `SHAFT-08-PLAN-06`
- Car and shaft data: `CAR-08-DATA-06`
- Population and accessibility schedule: `ACCESS-08-SCHED-06`
- Emergency lift rule: `LIFT-08-RULE-06`
- Power schedule: `POWER-08-SCHED-06`
- Vertical transport memo: `MEMO-08-VT-06`

## Source Values

| Item | Value |
|------|-------|
| Car internal width | {{ car_internal_width_m }} m |
| Required car width | {{ required_car_width_m }} m |
| Car internal depth | {{ car_internal_depth_m }} m |
| Required car depth | {{ required_car_depth_m }} m |
| Shaft width | {{ shaft_width_m }} m |
| Shaft depth | {{ shaft_depth_m }} m |
| Side clearance | {{ side_clearance_m }} m |
| Front/rear clearance | {{ front_rear_clearance_m }} m |
| Lift count | {{ lift_count }} |
| Car capacity | {{ car_capacity_persons }} persons |
| Loading factor | {{ loading_factor }} |
| Round-trip time | {{ round_trip_time_s }} s |
| Accessible demand | {{ accessible_demand_persons_per_5min }} persons/5min |
| Lift motor load | {{ lift_motor_kw }} kW |
| Fire-service lift count | {{ fire_service_lift_count }} |
| Controls load | {{ controls_load_kw }} kW |
| Generator allocation | {{ generator_allocation_kw }} kW |
| Voltage | {{ voltage_v }} V |
| Power factor | {{ power_factor }} |
| Feeder length | {{ feeder_length_km }} km |
| Feeder resistance | {{ feeder_resistance_ohm_per_km }} ohm/km |
| Feeder reactance | {{ feeder_reactance_ohm_per_km }} ohm/km |
| Allowable voltage drop | {{ allowable_voltage_drop_percent }} percent |

## Checks

- Car width and depth margins equal internal dimensions minus required dimensions.
- Shaft margins equal shaft dimensions minus car dimensions and required clearances.
- Accessible lift capacity equals `300 x lift_count x car_capacity x loading_factor / round_trip_time`.
- Accessible capacity margin equals accessible lift capacity minus accessible demand.
- Emergency power load equals fire-service lift motor load plus controls load.
- Generator allocation margin equals generator allocation minus emergency power load.
- Lift feeder current and voltage drop use three-phase voltage, power factor, feeder R/X, and length.
- Overall pass score is `1.0` only when car, shaft, accessibility, generator, and feeder checks pass; otherwise it is `0.0`.

## Output Format

Write a compact vertical transport memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "car_width_margin_m": <numeric_value>,
  "car_depth_margin_m": <numeric_value>,
  "shaft_width_margin_m": <numeric_value>,
  "shaft_depth_margin_m": <numeric_value>,
  "accessible_lift_capacity_persons_per_5min": <numeric_value>,
  "accessible_capacity_margin_persons_per_5min": <numeric_value>,
  "emergency_power_load_kw": <numeric_value>,
  "generator_allocation_margin_kw": <numeric_value>,
  "lift_feeder_current_a": <numeric_value>,
  "feeder_voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
