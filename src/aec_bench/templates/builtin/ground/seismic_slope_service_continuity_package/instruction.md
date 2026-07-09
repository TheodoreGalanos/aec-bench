You are checking a task-owned synthetic SSC-07 liquefaction/seismic slope and service continuity package for `SSC-07-LH-05`.

Use only the task-owned synthetic source pack values shown below for numeric grading.

## Source Pack

- Seismic design case: `SEIS-07-CASE-01`
- Slope section: `SLOPE-07-SECTION-01`
- Soil parameter table: `SOIL-07-SEIS-01`
- Utility and equipment layout: `UTIL-07-SERVICE-01`
- Resilience response memo: `MEMO-07-SEIS-01`

## Source Values

| Item | Value |
|---|---:|
| Slope angle | {{ slope_angle_deg }} degrees |
| Friction angle | {{ friction_angle_deg }} degrees |
| Cohesion | {{ cohesion_kpa }} kPa |
| Soil unit weight | {{ soil_unit_weight_kn_m3 }} kN/m3 |
| Failure depth | {{ failure_depth_m }} m |
| Seismic coefficient | {{ seismic_coefficient }} |
| Service load | {{ service_load_kw }} kW |
| Backup capacity | {{ backup_capacity_kw }} kW |
| Feeder current | {{ feeder_current_a }} A |
| Feeder resistance | {{ feeder_resistance_ohm_km }} ohm/km |
| Feeder length | {{ feeder_length_km }} km |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Allowable voltage drop | {{ allowable_voltage_drop_percent }} percent |

Compute pseudo-static slope resisting and driving terms, static and seismic factors of safety, service-capacity margin, feeder voltage drop, and voltage-drop margin.

Write a compact source-bound resilience response to `/workspace/output.md`. Preserve the source IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "slope_resisting_kpa": <numeric_value>,
  "static_driving_kpa": <numeric_value>,
  "seismic_increment_kpa": <numeric_value>,
  "static_slope_fs": <numeric_value>,
  "seismic_slope_fs": <numeric_value>,
  "seismic_fs_margin": <numeric_value>,
  "service_capacity_margin_kw": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
