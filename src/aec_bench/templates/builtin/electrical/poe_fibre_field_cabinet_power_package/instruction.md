You are an electrical design engineer checking `SSC-05-LH-06`, a task-owned synthetic SSC-05 PoE, fibre, and field cabinet power package.

Use only the task-owned synthetic source pack values below for numeric grading. PoE-budget, fibre-link, field-cabinet, and UPS autonomy workflows shape the context only; this instance does not run those tools or parse a real network topology, fibre loss sheet, or UPS export.

## Scene

- Design case: `CASE-SSC05-POE-FIBRE-06`
- Device schedule: `DEVICE-05-SCHED-06`
- Network topology: `NET-05-TOPO-06`
- PoE switch schedule: `POE-05-SWITCH-06`
- Fibre path table: `FIBRE-05-PATH-06`
- Battery or UPS data sheet: `UPS-05-CAB-06`
- Field cabinet memo: `MEMO-05-CABINET-06`

## Source Values

| Item | Value |
|------|-------|
| Camera count | {{ camera_count }} |
| Camera PoE allocation | {{ camera_poe_w }} W |
| Radio count | {{ radio_count }} |
| Radio PoE allocation | {{ radio_poe_w }} W |
| Controller count | {{ controller_count }} |
| Controller PoE allocation | {{ controller_poe_w }} W |
| PoE budget | {{ poe_budget_w }} W |
| UPS nominal energy | {{ ups_nominal_kwh }} kWh |
| UPS usable fraction | {{ ups_usable_fraction }} |
| Inverter efficiency | {{ inverter_efficiency }} |
| Non-PoE load | {{ non_poe_load_w }} W |
| Required runtime | {{ required_runtime_h }} h |
| Switch heat | {{ switch_heat_w }} W |
| Cabinet thermal dissipation | {{ cabinet_thermal_w_per_c }} W/C |
| Maximum temperature rise | {{ max_temperature_rise_c }} C |
| Fibre length | {{ fibre_length_km }} km |
| Fibre loss | {{ fibre_loss_db_per_km }} dB/km |
| Splice count | {{ splice_count }} |
| Splice loss | {{ splice_loss_db }} dB |
| Connector count | {{ connector_count }} |
| Connector loss | {{ connector_loss_db }} dB |
| Patch loss | {{ patch_loss_db }} dB |
| Optical budget | {{ optical_budget_db }} dB |

Checks:

- PoE load equals camera, radio, and controller PoE loads.
- Usable UPS energy equals `ups_nominal_kwh x ups_usable_fraction x inverter_efficiency`.
- UPS runtime equals usable UPS energy divided by PoE plus non-PoE load.
- Cabinet temperature rise equals cabinet heat divided by thermal dissipation.
- Fibre loss equals cable, splice, connector, and patch losses.
- Overall pass score is `1.0` only when PoE, runtime, temperature, and optical margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated software evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "poe_load_w": <numeric_value>,
  "poe_budget_margin_w": <numeric_value>,
  "usable_ups_energy_kwh": <numeric_value>,
  "ups_runtime_hr": <numeric_value>,
  "runtime_margin_hr": <numeric_value>,
  "cabinet_heat_w": <numeric_value>,
  "cabinet_temp_rise_c": <numeric_value>,
  "temperature_margin_c": <numeric_value>,
  "fibre_loss_db": <numeric_value>,
  "optical_margin_db": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
