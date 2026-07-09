You are a civil/transport engineer checking a task-owned synthetic SSC-08 pedestrian clearance, building forecourt, and signal interface package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External pedestrian clearance, all-red timing, forecourt density, discharge width, and lighting workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-08-LH-07`
- Station/forecourt plan: `FORECOURT-08-PLAN-07`
- Pedestrian demand schedule: `PED-08-DEMAND-07`
- Signal timing sheet: `SIGNAL-08-TIMING-07`
- Lighting layout: `LIGHT-08-LAYOUT-07`
- Road authority criterion: `AUTH-08-ROAD-07`
- Interface memo: `MEMO-08-INTERFACE-07`

## Source Values

| Item | Value |
|------|-------|
| Crossing length | {{ crossing_length_m }} m |
| Pedestrian speed | {{ pedestrian_speed_m_s }} m/s |
| Startup time | {{ startup_time_s }} s |
| Provided pedestrian phase | {{ provided_pedestrian_phase_s }} s |
| Approach speed | {{ approach_speed_kmh }} km/h |
| Crossing width | {{ crossing_width_m }} m |
| Reaction time | {{ reaction_time_s }} s |
| Provided all-red time | {{ provided_all_red_s }} s |
| Forecourt area | {{ forecourt_area_m2 }} m2 |
| Peak forecourt demand | {{ peak_forecourt_demand_persons }} persons |
| Maximum forecourt density | {{ maximum_forecourt_density_person_m2 }} persons/m2 |
| Discharge width factor | {{ discharge_width_factor_mm_per_person }} mm/person |
| Provided discharge width | {{ provided_discharge_width_mm }} mm |
| Luminaire lumens | {{ luminaire_lumens }} lm |
| Luminaire count | {{ luminaire_count }} |
| Light loss factor | {{ light_loss_factor }} |
| Utilization factor | {{ utilization_factor }} |
| Target illuminance | {{ target_illuminance_lux }} lux |

## Checks

- Pedestrian clearance time equals crossing length divided by pedestrian speed plus startup time.
- Pedestrian phase margin equals provided pedestrian phase minus clearance time.
- All-red time equals reaction time plus crossing width divided by approach speed.
- Forecourt density equals peak forecourt demand divided by forecourt area.
- Required discharge width equals peak forecourt demand times discharge width factor.
- Forecourt average illuminance uses luminaire lumens, count, light loss factor, utilization factor, and area.
- Overall pass score is `1.0` only when pedestrian phase, all-red, density, discharge width, and illuminance checks pass; otherwise it is `0.0`.

## Output Format

Write a compact interface memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pedestrian_clearance_time_s": <numeric_value>,
  "pedestrian_phase_margin_s": <numeric_value>,
  "all_red_time_s": <numeric_value>,
  "all_red_margin_s": <numeric_value>,
  "forecourt_density_person_m2": <numeric_value>,
  "forecourt_density_margin_person_m2": <numeric_value>,
  "required_discharge_width_mm": <numeric_value>,
  "discharge_width_margin_mm": <numeric_value>,
  "forecourt_average_illuminance_lux": <numeric_value>,
  "illuminance_margin_lux": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
