You are an electrical design engineer checking `SSC-05-LH-02`, a task-owned synthetic SSC-05 PV/BESS interconnection and export-control package.

Use only the task-owned synthetic source pack values below for numeric grading. ETAP, EasyPower, utility-interconnection, and export-control workflows shape the context only; this instance does not run those tools or parse a real SLD, utility rule, or inverter/BESS export.

## Scene

- Design case: `CASE-SSC05-PVBESS-02`
- PV module record: `PV-05-MOD-02`
- Inverter data sheet: `INV-05-DATA-02`
- BESS data sheet: `BESS-05-DATA-02`
- PCC and SLD definition: `PCC-05-SLD-02`
- Utility export-control rule: `RULE-05-EXPORT-02`
- Interconnection memo: `MEMO-05-INTERCON-02`

## Source Values

| Item | Value |
|------|-------|
| PV DC rating | {{ pv_dc_kw }} kW |
| DC-to-AC derate factor | {{ dc_ac_derate_factor }} |
| Inverter AC rating | {{ inverter_ac_kw }} kW |
| Site minimum load | {{ site_minimum_load_kw }} kW |
| Export limit | {{ export_limit_kw }} kW |
| BESS nominal energy | {{ bess_nominal_kwh }} kWh |
| BESS usable fraction | {{ bess_usable_fraction }} |
| BESS inverter efficiency | {{ bess_inverter_efficiency }} |
| Reserved energy | {{ reserved_energy_kwh }} kWh |
| Critical load | {{ critical_load_kw }} kW |
| Outage duration | {{ outage_duration_h }} h |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder power factor | {{ feeder_power_factor }} |
| Feeder length | {{ feeder_length_m }} m |
| Voltage-drop factor | {{ voltage_drop_mv_per_a_m }} mV/A/m |
| Breaker allowable current | {{ breaker_allowable_current_a }} A |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |

Checks:

- PV AC output equals `min(pv_dc_kw x dc_ac_derate_factor, inverter_ac_kw)`.
- Export equals `max(pv_ac_output_kw - site_minimum_load_kw, 0)`.
- Export excess equals `max(export_kw - export_limit_kw, 0)`.
- Usable BESS energy equals `bess_nominal_kwh x bess_usable_fraction x bess_inverter_efficiency - reserved_energy_kwh`.
- Backup energy required equals `critical_load_kw x outage_duration_h`.
- Feeder current equals `pv_ac_output_kw x 1000 / (sqrt(3) x feeder_voltage_v x feeder_power_factor)`.
- Voltage drop percent equals `voltage_drop_mv_per_a_m x feeder_current_a x feeder_length_m / 1000 / feeder_voltage_v x 100`.
- Overall pass score is `1.0` only when export, backup, voltage-drop, and breaker margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated ETAP/EasyPower evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pv_ac_output_kw": <numeric_value>,
  "export_kw": <numeric_value>,
  "export_excess_kw": <numeric_value>,
  "usable_bess_energy_kwh": <numeric_value>,
  "backup_energy_required_kwh": <numeric_value>,
  "backup_energy_margin_kwh": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_excess_percent": <numeric_value>,
  "breaker_margin_a": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
