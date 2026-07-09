You are a sports-field lighting engineer checking a task-owned synthetic SSC-13 power and uniformity package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External lighting design software and standards workflows shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-13-LH-03`
- Field layout: `FIELD-13-LAYOUT-03`
- Luminaire schedule: `LUM-13-SCHED-03`
- Calculation grid: `GRID-13-CALC-03`
- Power schedule: `POWER-13-SCHED-03`
- Operating mode: `CTRL-13-MODE-03`
- Lighting memo: `MEMO-13-FIELD-03`

All checks use the same field geometry, luminaire schedule, grid, operating mode, and feeder basis.

## Source Values

| Item | Value |
|------|-------|
| Grid lux values | {{ grid_lux_01 }}, {{ grid_lux_02 }}, {{ grid_lux_03 }}, {{ grid_lux_04 }}, {{ grid_lux_05 }}, {{ grid_lux_06 }}, {{ grid_lux_07 }}, {{ grid_lux_08 }} |
| Required average illuminance | {{ required_average_lux }} lux |
| Required uniformity | {{ required_uniformity_ratio }} |
| Luminaire count | {{ luminaire_count }} |
| Luminaire power | {{ luminaire_power_w }} W |
| Driver loss factor | {{ driver_loss_factor }} |
| Event duration | {{ event_hours }} h |
| Feeder voltage | {{ voltage_v }} V |
| Power factor | {{ power_factor }} |
| Feeder rating | {{ feeder_rating_a }} A |

## Output Format

Write a compact lighting memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "average_illuminance_lux": <numeric_value>,
  "minimum_illuminance_lux": <numeric_value>,
  "uniformity_ratio": <numeric_value>,
  "average_illuminance_margin_lux": <numeric_value>,
  "uniformity_margin": <numeric_value>,
  "connected_load_kw": <numeric_value>,
  "event_energy_kwh": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "feeder_current_margin_a": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
