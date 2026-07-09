You are a wastewater process engineer checking a task-owned synthetic SSC-10 chemical dosing, storage, and containment package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Chemical dosing, bund containment, pump selection, and 4-20 mA scaling workflows shape the context only; this instance does not parse a real source pack, vendor export, or authority-approved design.

## Scene

- Product: `SSC-10-LH-03`
- Process flow/load table: `FLOW-10-CHEM-03`
- Chemical dosing basis: `DOSE-10-BASIS-03`
- Tank/storage schedule: `TANK-10-STORAGE-03`
- Bund detail: `BUND-10-DETAIL-03`
- Pump/control schedule: `PUMP-10-CONTROL-03`
- Chemical system memo: `MEMO-10-CHEM-03`

## Source Values

| Item | Value |
| --- | --- |
| Process flow | {{ flow_rate_m3_d }} m3/d |
| Chemical dose | {{ chemical_dose_mg_l }} mg/L |
| Solution strength | {{ solution_strength_kg_l }} kg/L |
| Required storage | {{ required_storage_days }} d |
| Installed storage | {{ installed_storage_m3 }} m3 |
| Largest tank | {{ largest_tank_m3 }} m3 |
| Bund factor | {{ bund_factor }} |
| Rain allowance | {{ rain_allowance_m3 }} m3 |
| Available bund | {{ bund_available_m3 }} m3 |
| Pump operating hours | {{ pump_operating_hours_d }} h/d |
| Selected pump capacity | {{ selected_pump_capacity_l_h }} L/h |
| Signal range | {{ signal_range_l_h }} L/h |

## Calculation Rules

- Chemical mass equals `flow_rate_m3_d x chemical_dose_mg_l / 1000`.
- Solution volume equals chemical mass divided by solution strength.
- Required storage equals daily solution volume times required storage days.
- Refill margin equals installed storage duration minus required storage duration.
- Bund required equals largest tank times bund factor plus rain allowance.
- Dosing pump flow equals daily solution volume divided by pump operating hours.
- Design signal equals `4 + 16 x dosing_pump_flow_l_h / signal_range_l_h`.
- Overall pass score is `1.0` only when refill, bund, pump capacity, and signal headroom margins are non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "chemical_mass_kg_d": <numeric_value>,
  "solution_volume_l_d": <numeric_value>,
  "required_storage_m3": <numeric_value>,
  "refill_margin_d": <numeric_value>,
  "bund_required_m3": <numeric_value>,
  "bund_margin_m3": <numeric_value>,
  "dosing_pump_flow_l_h": <numeric_value>,
  "pump_capacity_margin_l_h": <numeric_value>,
  "design_signal_ma": <numeric_value>,
  "signal_headroom_ma": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
