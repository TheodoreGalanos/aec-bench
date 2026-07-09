You are a coastal mechanical engineer checking a task-owned synthetic SSC-06 marine or coastal pumping equipment package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Coastal/tidal boundary, pump selection, backup generator, freeboard, and corrosion workflows shape the context only; this instance does not run external software or parse a real source pack.

## Scene

- Product: `SSC-06-LH-07`
- Tide/tailwater table: `TIDE-06-TAILWATER-07`
- Pump station section: `SECTION-06-PUMP-07`
- Pipe schedule: `PIPE-06-SCHED-07`
- Motor/load schedule: `MOTOR-06-SCHED-07`
- Materials or corrosion note: `MATERIAL-06-CORROSION-07`
- Coastal equipment memo: `MEMO-06-COASTAL-07`

## Source Values

| Item | Value |
| --- | --- |
| Pump flow | {{ pump_flow_l_s }} L/s |
| Static lift | {{ static_lift_m }} m |
| Tailwater surcharge | {{ tailwater_surcharge_m }} m |
| Pipe loss | {{ pipe_loss_m }} m |
| Flap-gate loss | {{ flap_gate_loss_m }} m |
| Seawater density | {{ seawater_density_kg_m3 }} kg/m3 |
| Pump efficiency | {{ pump_efficiency }} |
| Motor efficiency | {{ motor_efficiency }} |
| Controls load | {{ controls_load_kw }} kW |
| Generator capacity | {{ generator_capacity_kw }} kW |
| Fuel available | {{ fuel_available_l }} L |
| Generator energy | {{ generator_energy_kwh_per_l }} kWh/L |
| Equipment elevation | {{ equipment_elevation_m }} m |
| Design flood level | {{ design_flood_level_m }} m |
| Minimum freeboard | {{ minimum_freeboard_m }} m |
| Corrosion allowance | {{ corrosion_allowance_mm }} mm |
| Required corrosion allowance | {{ required_corrosion_allowance_mm }} mm |

## Calculation Rules

- Total pumping head equals static lift plus tailwater surcharge plus pipe loss plus flap-gate loss.
- Pump hydraulic power equals `seawater_density_kg_m3 x 9.81 x flow_m3_s x total_pumping_head_m / 1000`.
- Pump input power equals hydraulic power divided by pump and motor efficiencies.
- Backup generator load equals pump input power plus controls load.
- Generator capacity margin equals generator capacity minus backup generator load.
- Backup runtime equals fuel available times generator energy per litre divided by backup generator load.
- Equipment freeboard equals equipment elevation minus design flood level.
- Equipment freeboard margin equals equipment freeboard minus minimum freeboard.
- Corrosion allowance margin equals provided corrosion allowance minus required corrosion allowance.
- Overall pass score is `1.0` only when generator, freeboard, and corrosion margins are non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "total_pumping_head_m": <numeric_value>,
  "pump_hydraulic_power_kw": <numeric_value>,
  "pump_input_power_kw": <numeric_value>,
  "backup_generator_load_kw": <numeric_value>,
  "generator_capacity_margin_kw": <numeric_value>,
  "backup_runtime_hr": <numeric_value>,
  "equipment_freeboard_m": <numeric_value>,
  "equipment_freeboard_margin_m": <numeric_value>,
  "corrosion_allowance_margin_mm": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
