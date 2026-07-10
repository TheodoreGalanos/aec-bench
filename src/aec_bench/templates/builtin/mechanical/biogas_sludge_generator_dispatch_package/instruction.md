You are a wastewater process engineer checking a task-owned synthetic SSC-10 biogas, sludge, and generator dispatch package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Sludge production, digester gas metering, generator data sheet, load profile, and dispatch-policy workflows shape the context only; this instance does not parse a real process model, gas meter export, or accepted project report.

## Scene

- Product: `SSC-10-LH-07`
- Sludge production table: `SLUDGE-10-PROD-07`
- Digester/gas meter data: `DIGESTER-10-GAS-07`
- Generator data sheet: `GEN-10-DATA-07`
- Load profile: `LOAD-10-PROFILE-07`
- Operating policy: `POLICY-10-DISPATCH-07`
- Dispatch memo: `MEMO-10-DISPATCH-07`

## Source Values

| Item | Value |
| --- | --- |
| Sludge production | {{ sludge_production_kg_d }} kg/d |
| Volatile solids fraction | {{ volatile_solids_fraction }} |
| Volatile solids destruction | {{ volatile_solids_destruction_fraction }} |
| Biogas yield | {{ biogas_yield_m3_kg_vs }} m3/kg VS |
| Methane fraction | {{ methane_fraction }} |
| Methane energy | {{ methane_energy_kwh_m3 }} kWh/m3 |
| Generator electrical efficiency | {{ generator_electrical_efficiency }} |
| Generator rating | {{ generator_rated_kw }} kW |
| Critical process load | {{ critical_process_load_kw }} kW |
| Dispatch runtime | {{ dispatch_runtime_h }} h |
| Parasitic load | {{ parasitic_load_kw }} kW |
| Heat recovery efficiency | {{ heat_recovery_efficiency }} |
| Heat load to offset | {{ heat_load_kwh_d }} kWh/d |

## Calculation Rules

- Volatile solids feed equals sludge production times volatile solids fraction.
- Volatile solids destroyed equals volatile solids feed times destruction fraction.
- Biogas volume equals volatile solids destroyed times biogas yield.
- Methane energy equals methane volume times methane energy content.
- Generator electric energy equals methane energy times generator electrical efficiency.
- Available runtime equals generator electric energy divided by critical plus parasitic load.
- Overall pass score is `1.0` only when generator capacity, dispatch energy, and heat recovery margins are non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "volatile_solids_feed_kg_d": <numeric_value>,
  "volatile_solids_destroyed_kg_d": <numeric_value>,
  "biogas_m3_d": <numeric_value>,
  "methane_m3_d": <numeric_value>,
  "methane_energy_kwh_d": <numeric_value>,
  "generator_electric_energy_kwh_d": <numeric_value>,
  "average_generator_kw": <numeric_value>,
  "generator_capacity_margin_kw": <numeric_value>,
  "critical_dispatch_energy_kwh": <numeric_value>,
  "dispatch_energy_margin_kwh": <numeric_value>,
  "available_runtime_hr": <numeric_value>,
  "heat_recovery_kwh_d": <numeric_value>,
  "heat_recovery_margin_kwh_d": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
