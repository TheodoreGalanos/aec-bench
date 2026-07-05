You are a rail communications and power engineer checking `SSC-02-LH-07`, a task-owned synthetic SSC-02 wayside cabinet load, communications, and backup supply package.

Use only the task-owned synthetic source pack values below for numeric grading. Wayside cabinet power, fiber link budget, and backup-power workflows shape the context only; this instance does not parse a real cabinet drawing, network model, or UPS datasheet.

## Scene

- Design case: `CASE-SSC02-CAB-07`
- Cabinet layout: `CAB-02-LAYOUT-07`
- Device load schedule: `LOAD-02-DEVICE-07`
- Communications topology: `COMMS-02-TOPO-07`
- UPS data sheet: `UPS-02-DATA-07`
- Maintenance response plan: `MAINT-02-RESPONSE-07`
- Resilience memo: `MEMO-02-RESILIENCE-07`

## Source Values

| Item | Value |
|------|-------|
| Signal processor load | {{ signal_processor_w }} W |
| Axle counter load | {{ axle_counter_w }} W |
| Communications switch load | {{ comms_switch_w }} W |
| Radio load | {{ radio_w }} W |
| Point machine heater load | {{ point_machine_heater_w }} W |
| Spare allowance | {{ spare_allowance_pct }} % |
| Autonomy | {{ autonomy_h }} h |
| DC voltage | {{ dc_voltage_v }} V |
| Usable battery fraction | {{ usable_battery_fraction }} |
| Installed battery capacity | {{ installed_battery_ah }} Ah |
| Feeder length | {{ feeder_length_m }} m |
| Conductor resistance | {{ conductor_resistance_milliohm_per_m }} milliohm/m |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |
| Fiber length | {{ fiber_length_km }} km |
| Fiber attenuation | {{ fiber_attenuation_db_per_km }} dB/km |
| Connector count | {{ fiber_connector_count }} |
| Connector loss | {{ connector_loss_db }} dB |
| Splice count | {{ fiber_splice_count }} |
| Splice loss | {{ splice_loss_db }} dB |
| Patch panel allowance | {{ patch_panel_allowance_db }} dB |
| Optical transmitter power | {{ optical_tx_power_dbm }} dBm |
| Receiver sensitivity | {{ receiver_sensitivity_dbm }} dBm |
| Required fiber margin | {{ required_fiber_margin_db }} dB |
| Selected UPS rating | {{ selected_ups_rating_va }} VA |
| Load power factor | {{ load_power_factor }} |

Checks:

- Connected load equals the sum of the five device loads.
- Design load equals connected load times one plus spare allowance.
- Required battery capacity equals `design_load x autonomy / (dc_voltage x usable_fraction)`.
- DC feeder voltage drop uses two-wire length, current, and conductor resistance.
- Fiber link margin uses attenuation, connector loss, splice loss, patch loss, transmitter power, and receiver sensitivity.
- Overall pass score is `1.0` only when battery, feeder, fiber, and UPS margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, network model validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "connected_load_w": <numeric_value>,
  "design_load_w": <numeric_value>,
  "required_energy_kwh": <numeric_value>,
  "required_battery_capacity_ah": <numeric_value>,
  "battery_capacity_margin_ah": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "feeder_voltage_drop_v": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "fiber_total_loss_db": <numeric_value>,
  "fiber_receive_power_dbm": <numeric_value>,
  "fiber_link_margin_db": <numeric_value>,
  "fiber_excess_margin_db": <numeric_value>,
  "required_ups_rating_va": <numeric_value>,
  "ups_rating_margin_va": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
