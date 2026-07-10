You are a wastewater process engineer checking a task-owned synthetic SSC-10 wet-weather process and bypass resilience package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Wet-weather process, storage, pump backup energy, control rules, and bypass-permit workflows shape the context only; this instance does not parse a real hydraulic model, permit file, or accepted project report.

## Scene

- Product: `SSC-10-LH-06`
- Wet-weather inflow table: `WET-10-INFLOW-06`
- Process unit schedule: `UNIT-10-SCHED-06`
- Pump/storage schedule: `PUMP-10-STORAGE-06`
- Control rules: `CONTROL-10-RULES-06`
- Permit criterion: `PERMIT-10-BYPASS-06`
- Wet-weather memo: `MEMO-10-WET-06`

## Source Values

| Item | Value |
| --- | --- |
| Peak inflow | {{ peak_inflow_m3_h }} m3/h |
| Process capacity | {{ process_capacity_m3_h }} m3/h |
| Peak duration | {{ peak_duration_h }} h |
| Reactor volume | {{ reactor_volume_m3 }} m3 |
| Minimum HRT | {{ min_hrt_hr }} h |
| Clarifier area | {{ clarifier_area_m2 }} m2 |
| Maximum peak SOR | {{ max_peak_sor_m3_m2_d }} m3/m2/d |
| Available storage | {{ available_storage_m3 }} m3 |
| Pump head | {{ pump_head_m }} m |
| Pump efficiency | {{ pump_efficiency }} |
| Pump motor efficiency | {{ pump_motor_efficiency }} |
| Backup BESS | {{ backup_bess_kwh }} kWh |
| BESS usable SOC | {{ bess_usable_soc_fraction }} |
| BESS inverter efficiency | {{ bess_inverter_efficiency }} |
| BESS reserve | {{ bess_reserve_kwh }} kWh |
| Outage duration | {{ outage_duration_h }} h |
| Allowed bypass | {{ allowed_bypass_m3 }} m3 |

## Calculation Rules

- Required storage equals excess wet-weather flow times peak duration.
- Reactor HRT equals reactor volume divided by peak inflow.
- Clarifier peak SOR equals peak inflow times 24 divided by clarifier area.
- Pump input power uses water density, gravity, flow, pump head, pump efficiency, and motor efficiency.
- Usable backup energy equals BESS capacity times usable SOC times inverter efficiency minus reserve.
- Bypass volume equals any excess flow that remains after process capacity and storage are exhausted.
- Overall pass score is `1.0` only when storage, HRT, SOR, backup-energy, and bypass margins are non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "required_storage_m3": <numeric_value>,
  "storage_margin_m3": <numeric_value>,
  "reactor_hrt_hr": <numeric_value>,
  "hrt_margin_hr": <numeric_value>,
  "clarifier_peak_sor_m3_m2_d": <numeric_value>,
  "sor_margin_m3_m2_d": <numeric_value>,
  "pump_input_power_kw": <numeric_value>,
  "outage_energy_kwh": <numeric_value>,
  "usable_backup_energy_kwh": <numeric_value>,
  "backup_energy_margin_kwh": <numeric_value>,
  "bypass_volume_m3": <numeric_value>,
  "bypass_margin_m3": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
