You are a structural/marine engineer checking a task-owned synthetic SSC-04 marine berthing, fender, and storm operations package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External berthing-energy, fender, mooring, tide, weather, and port-operations workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-04-LH-03`
- Vessel data sheet: `VESSEL-04-DATA-03`
- Berth layout: `BERTH-04-LAYOUT-03`
- Fender schedule: `FENDER-04-SCHED-03`
- Mooring schedule: `MOORING-04-SCHED-03`
- Tide and weather table: `TIDE-04-WEATHER-03`
- Marine operations memo: `MEMO-04-MARINE-03`

## Source Values

| Item | Value |
|------|-------|
| Vessel mass | {{ vessel_mass_t }} t |
| Approach velocity | {{ approach_velocity_m_s }} m/s |
| Eccentricity factor | {{ eccentricity_factor }} |
| Softness factor | {{ softness_factor }} |
| Fender energy capacity | {{ fender_energy_capacity_knm }} kNm |
| Wind pressure | {{ wind_pressure_kpa }} kPa |
| Projected area | {{ projected_area_m2 }} m2 |
| Current load | {{ current_load_kn }} kN |
| Mooring line count | {{ mooring_line_count }} |
| Mooring line capacity | {{ mooring_line_capacity_kn }} kN |
| Mooring efficiency | {{ mooring_efficiency }} |
| Storm tide operating level | {{ storm_tide_level_m }} m |
| Deck level | {{ deck_level_m }} m |
| Required deck clearance | {{ required_deck_clearance_m }} m |
| Allowable downtime | {{ allowable_downtime_h }} h |
| Tide exceedance duration | {{ tide_exceedance_h }} h |

## Checks

- Berthing energy equals `0.5 x vessel_mass_t x approach_velocity_m_s^2 x eccentricity_factor x softness_factor`.
- Fender margin equals fender energy capacity minus berthing energy.
- Environmental mooring load equals wind pressure times projected area plus current load.
- Mooring capacity equals line count times line capacity times mooring efficiency.
- Deck clearance margin equals deck level minus storm tide operating level and required clearance.
- Operating window margin equals allowable downtime minus tide exceedance duration.
- Overall pass score is `1.0` only when fender, mooring, deck clearance, and operating-window margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact marine operations memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "berthing_energy_knm": <numeric_value>,
  "fender_energy_margin_knm": <numeric_value>,
  "environmental_mooring_load_kn": <numeric_value>,
  "mooring_capacity_kn": <numeric_value>,
  "mooring_margin_kn": <numeric_value>,
  "storm_tide_operating_level_m": <numeric_value>,
  "deck_clearance_margin_m": <numeric_value>,
  "allowable_operating_window_margin_h": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
