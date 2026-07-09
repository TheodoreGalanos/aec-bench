You are checking a task-owned synthetic SSC-07 excavation/dewatering and temporary power safety package for `SSC-07-LH-04`.

Use only the task-owned synthetic source pack values shown below for numeric grading.

## Source Pack

- Excavation section: `EXC-07-SECTION-01`
- Groundwater record: `GW-07-DEWATER-01`
- Temporary pump schedule: `PUMP-07-TEMP-01`
- Temporary power layout: `PWR-07-TEMP-01`
- Temporary works memo: `MEMO-07-TEMP-01`

## Source Values

| Item | Value |
|---|---:|
| Water head above base | {{ water_head_above_base_m }} m |
| Seepage path | {{ seepage_path_m }} m |
| Critical gradient | {{ critical_gradient }} |
| Excavation slope angle | {{ slope_angle_deg }} degrees |
| Soil friction angle | {{ friction_angle_deg }} degrees |
| Pore pressure ratio | {{ pore_pressure_ratio }} |
| Pump flow | {{ pump_flow_m3_s }} m3/s |
| Pump head | {{ pump_head_m }} m |
| Pump efficiency | {{ pump_efficiency }} |
| Pump count | {{ pump_count }} |
| Controls load | {{ controls_load_kw }} kW |
| Generator capacity | {{ generator_capacity_kw }} kW |
| Battery capacity | {{ battery_capacity_kwh }} kWh |
| Autonomy load | {{ autonomy_load_kw }} kW |
| Required runtime | {{ required_runtime_h }} h |
| Slab resisting pressure | {{ slab_resisting_pressure_kpa }} kPa |

Compute exit-gradient safety, rapid-drawdown slope safety, pump power, temporary power, generator margin, battery runtime, uplift pressure, and uplift margin.

Write a compact source-bound temporary works memo to `/workspace/output.md`. Preserve the source IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "exit_gradient": <numeric_value>,
  "exit_gradient_fs": <numeric_value>,
  "rapid_drawdown_fs": <numeric_value>,
  "pump_power_kw": <numeric_value>,
  "temporary_power_kw": <numeric_value>,
  "generator_margin_kw": <numeric_value>,
  "battery_runtime_h": <numeric_value>,
  "battery_runtime_margin_h": <numeric_value>,
  "uplift_pressure_kpa": <numeric_value>,
  "uplift_margin_kpa": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
