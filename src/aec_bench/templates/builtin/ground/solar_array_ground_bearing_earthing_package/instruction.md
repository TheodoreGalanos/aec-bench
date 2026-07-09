You are checking a task-owned synthetic SSC-07 solar array wind load, ground bearing, and earthing package for `SSC-07-LH-03`.

Use only the task-owned synthetic source pack values shown below for numeric grading.

## Source Pack

- PV layout: `PV-07-ARRAY-01`
- Wind criteria: `WIND-07-PV-01`
- Rack and foundation schedule: `RACK-07-FOUND-01`
- Resistivity and earthing test area: `RES-07-PV-01`
- PV foundation safety memo: `MEMO-07-PV-01`

## Source Values

| Item | Value |
|---|---:|
| Wind pressure | {{ wind_pressure_kpa }} kPa |
| Module area | {{ module_area_m2 }} m2 |
| Drag coefficient | {{ drag_coefficient }} |
| Module count | {{ module_count }} |
| Support count | {{ support_count }} |
| Ballast dead load | {{ ballast_dead_load_kn }} kN |
| Footing area | {{ footing_area_m2 }} m2 |
| Allowable bearing | {{ allowable_bearing_kpa }} kPa |
| Soil resistivity | {{ soil_resistivity_ohm_m }} ohm-m |
| Grounding grid length | {{ grid_length_m }} m |
| Grounding grid width | {{ grid_width_m }} m |
| Buried conductor length | {{ conductor_length_m }} m |
| Grid current | {{ grid_current_ka }} kA |
| GPR limit | {{ gpr_limit_v }} V |

Compute total wind force, support reaction, uplift force and margin, bearing pressure and utilization, grid resistance, ground potential rise, and GPR margin.

Write a compact source-bound PV foundation safety memo to `/workspace/output.md`. Preserve the source IDs above. Include a source-boundary statement that this is a task-owned synthetic source pack.

Do not claim authority approval, accepted project evidence, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "wind_force_total_kn": <numeric_value>,
  "support_reaction_kn": <numeric_value>,
  "uplift_force_kn": <numeric_value>,
  "uplift_margin_kn": <numeric_value>,
  "bearing_pressure_kpa": <numeric_value>,
  "bearing_utilization": <numeric_value>,
  "grid_resistance_ohm": <numeric_value>,
  "ground_potential_rise_v": <numeric_value>,
  "gpr_margin_v": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
