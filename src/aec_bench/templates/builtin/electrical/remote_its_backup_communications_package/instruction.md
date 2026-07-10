You are an ITS communications engineer checking a task-owned synthetic SSC-13 remote backup communications package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External RF, fibre, ITS, and battery tools shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-13-LH-04`
- Device inventory: `DEV-13-INV-04`
- RF link sheet: `RF-13-LINK-04`
- Fibre topology: `FIB-13-TOPO-04`
- Bandwidth table: `BW-13-TABLE-04`
- Battery data sheet: `PWR-13-BAT-04`
- Communications resilience memo: `MEMO-13-REMOTE-04`

All checks use the same remote device inventory, RF/fibre topology, bandwidth table, PoE loads, and backup-power basis.

## Source Values

| Item | Value |
|------|-------|
| RF transmit power | {{ rf_tx_power_dbm }} dBm |
| RF transmit/receive gain | {{ rf_tx_gain_db }} dB / {{ rf_rx_gain_db }} dB |
| RF path and misc loss | {{ rf_path_loss_db }} dB / {{ rf_misc_loss_db }} dB |
| Receiver sensitivity | {{ rf_receiver_sensitivity_dbm }} dBm |
| Fibre length and attenuation | {{ fibre_length_km }} km at {{ fibre_loss_db_per_km }} dB/km |
| Connector count/loss | {{ connector_count }} at {{ connector_loss_db }} dB |
| Splice count/loss | {{ splice_count }} at {{ splice_loss_db }} dB |
| Reserve loss and budget | {{ reserve_loss_db }} dB / {{ fibre_budget_db }} dB |
| Network loads | CCTV {{ cctv_network_mbps }} Mbps, VMS {{ vms_network_mbps }} Mbps, sensor {{ sensor_network_mbps }} Mbps, controller {{ controller_network_mbps }} Mbps |
| Network overhead and capacity | {{ network_overhead_factor }} / {{ backhaul_capacity_mbps }} Mbps |
| PoE loads | {{ camera_count }} cameras at {{ camera_poe_w }} W, radio {{ radio_poe_w }} W, VMS {{ vms_poe_w }} W, sensor {{ sensor_poe_w }} W |
| PoE budget | {{ poe_budget_w }} W |
| Backup load/autonomy | {{ backup_load_w }} W for {{ autonomy_h }} h |
| Inverter efficiency/DOD/battery | {{ inverter_efficiency }}, {{ allowable_depth_of_discharge }}, {{ battery_capacity_kwh }} kWh |

## Output Format

Write a compact communications resilience memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "rf_received_power_dbm": <numeric_value>,
  "rf_fade_margin_db": <numeric_value>,
  "fibre_loss_db": <numeric_value>,
  "fibre_margin_db": <numeric_value>,
  "network_load_mbps": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "poe_load_w": <numeric_value>,
  "poe_headroom_w": <numeric_value>,
  "battery_required_kwh": <numeric_value>,
  "battery_margin_kwh": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
