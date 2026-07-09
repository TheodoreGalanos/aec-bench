You are a process and energy resilience engineer checking a task-owned synthetic SSC-17 wastewater energy island package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Process modelling, biogas, and BESS workflows shape the context only: this instance does not run external software or a real source-pack parser.

## Scene

- Product: `SSC-17-LH-02`
- Influent/effluent sample table: `WWTP-SSC17-002`
- PFD/process basis: `PFD-SSC17-002`
- Blower/motor schedule: `BLOWER-SSC17-002`
- Biogas/sludge record: `BIOGAS-SSC17-002`
- PV/BESS/feeder schedule: `BESS-SSC17-002`
- Critical-process resilience memo: `MEMO-SSC17-002`

## Source Values

| Item | Value |
| --- | --- |
| Influent flow | {{ influent_flow_mld }} ML/d |
| BOD | {{ bod_mg_l }} mg/L |
| Ammonia | {{ ammonia_mg_l }} mg/L |
| BOD oxygen factor | {{ bod_oxygen_factor }} kg O2/kg BOD |
| Nitrification oxygen factor | {{ nitrification_oxygen_factor }} kg O2/kg N |
| Blower specific energy | {{ blower_specific_energy_kwh_kg_o2 }} kWh/kg O2 |
| Auxiliary critical load | {{ auxiliary_critical_load_kw }} kW |
| Outage duration | {{ outage_duration_hr }} h |
| Volatile solids | {{ volatile_solids_kg_d }} kg/d |
| Biogas yield | {{ biogas_yield_m3_kg_vs }} m3/kg VS |
| Methane fraction | {{ methane_fraction }} |
| Methane energy | {{ methane_energy_kwh_m3 }} kWh/m3 |
| CHP efficiency | {{ chp_efficiency }} |
| BESS nominal energy | {{ bess_nominal_kwh }} kWh |
| Maximum depth of discharge | {{ max_depth_of_discharge }} |
| Inverter efficiency | {{ inverter_efficiency }} |

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "oxygen_demand_kg_d": <numeric_value>,
  "blower_energy_kwh_d": <numeric_value>,
  "blower_average_kw": <numeric_value>,
  "biogas_production_m3_d": <numeric_value>,
  "chp_energy_available_kwh": <numeric_value>,
  "bess_usable_energy_kwh": <numeric_value>,
  "critical_process_energy_kwh": <numeric_value>,
  "resilience_energy_available_kwh": <numeric_value>,
  "energy_margin_kwh": <numeric_value>,
  "battery_only_runtime_hr": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
