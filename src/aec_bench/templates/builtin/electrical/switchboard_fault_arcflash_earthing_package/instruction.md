You are an electrical design engineer checking `SSC-05-LH-03`, a task-owned synthetic SSC-05 switchboard fault, arc-flash, and earthing package.

Use only the task-owned synthetic source pack values below for numeric grading. ETAP, EasyPower, SKM PowerTools, arc-flash, and earthing workflows shape the context only; this instance does not run those tools or parse a real SLD, relay curve, fault-study export, or earthing model.

## Scene

- Design case: `CASE-SSC05-SWBD-03`
- Single-line diagram: `SLD-05-SWBD-03`
- Fault study table: `FAULT-05-STUDY-03`
- Relay/protection setting sheet: `RELAY-05-SET-03`
- Soil and earthing record: `EARTH-05-SOIL-03`
- Switchboard layout: `LAYOUT-05-SWBD-03`
- Safety note: `NOTE-05-SAFETY-03`

## Source Values

| Item | Value |
|------|-------|
| Utility fault level | {{ utility_fault_mva }} MVA |
| Switchboard voltage | {{ switchboard_voltage_v }} V |
| Transformer contribution | {{ transformer_contribution_ka }} kA |
| Motor contribution | {{ motor_contribution_ka }} kA |
| Switchboard fault rating | {{ switchboard_fault_rating_ka }} kA |
| Arcing-current factor | {{ arcing_current_factor }} |
| Clearing time | {{ clearing_time_s }} s |
| Incident-energy factor | {{ incident_energy_factor }} |
| Working distance | {{ working_distance_m }} m |
| Allowable incident energy | {{ allowable_incident_energy_cal_cm2 }} cal/cm2 |
| Earth-grid resistance | {{ earth_grid_resistance_ohm }} ohm |
| Touch-voltage limit | {{ touch_voltage_limit_v }} V |
| Busbar force factor | {{ busbar_force_factor }} |
| Busbar force rating | {{ busbar_force_rating_kn }} kN |

Checks:

- Utility fault current equals `utility_fault_mva x 1000 / (sqrt(3) x switchboard_voltage_v)`.
- Total fault current adds utility, transformer, and motor contributions.
- Incident energy equals `total_fault_current_ka x arcing_current_factor x clearing_time_s x incident_energy_factor / working_distance_m^2`.
- Touch voltage equals `total_fault_current_ka x 1000 x earth_grid_resistance_ohm`.
- Busbar force equals `busbar_force_factor x total_fault_current_ka^2`.
- Overall pass score is `1.0` only when fault-rating, incident-energy, touch-voltage, and busbar-force margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated ETAP/EasyPower/SKM evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "utility_fault_current_ka": <numeric_value>,
  "total_fault_current_ka": <numeric_value>,
  "fault_rating_margin_ka": <numeric_value>,
  "incident_energy_cal_cm2": <numeric_value>,
  "incident_energy_margin_cal_cm2": <numeric_value>,
  "touch_voltage_v": <numeric_value>,
  "touch_voltage_margin_v": <numeric_value>,
  "busbar_force_kn": <numeric_value>,
  "busbar_force_margin_kn": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
