You are a lighting and emergency-mode reviewer checking a task-owned synthetic SSC-13 lighting energy package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External lighting, LENI, emergency-lighting, and backup-power tools shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-13-LH-07`
- Lighting layout: `LIGHT-13-LAYOUT-07`
- Control schedule: `CTRL-13-SCHED-07`
- LENI/energy profile: `LENI-13-PROFILE-07`
- Emergency load schedule: `EMERG-13-LOAD-07`
- Criteria table: `CRIT-13-TABLE-07`
- Lighting-energy memo: `MEMO-13-ENERGY-07`

All checks use the same lighting grid, controls, energy profile, emergency load schedule, and criteria table.

## Source Values

| Item | Value |
|------|-------|
| Lighting grid lux values | {{ grid_lux_01 }}, {{ grid_lux_02 }}, {{ grid_lux_03 }}, {{ grid_lux_04 }}, {{ grid_lux_05 }}, {{ grid_lux_06 }} |
| Required normal/emergency illuminance | {{ required_illuminance_lux }} lux / {{ required_emergency_illuminance_lux }} lux |
| Emergency illuminance | {{ emergency_illuminance_lux }} lux |
| Luminaire count and normal power | {{ luminaire_count }} at {{ normal_luminaire_power_w }} W |
| Control factor and annual hours | {{ control_factor }} / {{ annual_operating_hours }} h |
| Area and LENI target | {{ area_m2 }} m2 / {{ target_leni_kwh_m2_year }} kWh/m2-year |
| Emergency luminaire power | {{ emergency_luminaire_power_w }} W each |
| Exit sign count and power | {{ exit_sign_count }} at {{ exit_sign_power_w }} W |
| Emergency autonomy and battery efficiency | {{ emergency_autonomy_h }} h / {{ battery_efficiency }} |
| Battery capacity | {{ battery_capacity_kwh }} kWh |

## Output Format

Write a compact lighting-energy memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "average_illuminance_lux": <numeric_value>,
  "minimum_illuminance_lux": <numeric_value>,
  "uniformity_ratio": <numeric_value>,
  "illuminance_margin_lux": <numeric_value>,
  "emergency_illuminance_margin_lux": <numeric_value>,
  "annual_lighting_energy_kwh": <numeric_value>,
  "leni_kwh_m2_year": <numeric_value>,
  "leni_margin_kwh_m2_year": <numeric_value>,
  "emergency_battery_required_kwh": <numeric_value>,
  "emergency_battery_margin_kwh": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
