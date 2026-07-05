You are a construction monitoring engineer checking a task-owned synthetic SSC-16 package for sensor data continuity, RF link margin, PoE load, battery/solar autonomy, and temporary DC voltage drop.

Use only the task-owned synthetic source pack values shown below for numeric grading. External telemetry, RF link-budget, monitoring, and inspection-reporting workflows shape the context only; they are not extra data sources for this instance.

## Source Objects

- Product: `SSC-16-LH-07`
- Monitoring layout: `MON-16-LAYOUT-07`
- Sensor schedule: `SENSOR-16-SCHED-07`
- Network topology: `NET-16-TOPO-07`
- Battery/solar datasheet: `BAT-16-SOLAR-07`
- Reporting rule: `REPORT-16-RULE-07`
- Monitoring continuity memo: `MEMO-16-MONITOR-07`

## Source Values

| Item | Value |
|------|-------|
| Turbidity sensor count | {{ turbidity_sensor_count }} |
| Turbidity sensor data | {{ turbidity_sensor_data_mbps }} Mbps |
| Vibration sensor count | {{ vibration_sensor_count }} |
| Vibration sensor data | {{ vibration_sensor_data_mbps }} Mbps |
| Camera count | {{ camera_count }} |
| Camera data | {{ camera_data_mbps }} Mbps |
| Weather station data | {{ weather_station_data_mbps }} Mbps |
| Gateway overhead | {{ gateway_overhead_mbps }} Mbps |
| Network capacity | {{ network_capacity_mbps }} Mbps |
| RF TX power | {{ rf_tx_power_dbm }} dBm |
| RF TX gain | {{ rf_tx_gain_db }} dB |
| RF RX gain | {{ rf_rx_gain_db }} dB |
| RF path loss | {{ rf_path_loss_db }} dB |
| RF miscellaneous loss | {{ rf_misc_loss_db }} dB |
| Receiver sensitivity | {{ rf_receiver_sensitivity_dbm }} dBm |
| Camera PoE load | {{ camera_poe_w }} W |
| Gateway PoE load | {{ gateway_poe_w }} W |
| Sensor PoE load | {{ sensor_poe_w }} W |
| PoE budget | {{ poe_budget_w }} W |
| Battery capacity | {{ battery_capacity_kwh }} kWh |
| Usable battery fraction | {{ usable_battery_fraction }} |
| Backup runtime | {{ backup_runtime_h }} h |
| Solar panel power | {{ solar_panel_power_w }} W |
| Peak sun hours | {{ peak_sun_hours }} h |
| Solar derate factor | {{ solar_derate_factor }} |
| DC voltage | {{ dc_voltage_v }} V |
| Feeder length | {{ feeder_length_km }} km |
| Feeder resistance | {{ feeder_resistance_ohm_km }} ohm/km |
| Allowed voltage drop | {{ allowed_voltage_drop_percent }} percent |

## Required Checks

- Sensor data load is the sum of sensor, camera, weather, and gateway data loads.
- RF received power equals TX power plus gains minus path and miscellaneous losses.
- PoE load is the sum of cameras, gateway, and scheduled sensor loads.
- Battery energy covers PoE load over the backup runtime.
- Solar daily headroom and temporary DC voltage-drop margin must remain non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack, preserve the source object IDs above, and state whether the baseline checks pass.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "sensor_data_load_mbps": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "rf_received_power_dbm": <numeric_value>,
  "rf_fade_margin_db": <numeric_value>,
  "poe_load_w": <numeric_value>,
  "poe_headroom_w": <numeric_value>,
  "battery_required_kwh": <numeric_value>,
  "battery_margin_kwh": <numeric_value>,
  "solar_daily_headroom_wh": <numeric_value>,
  "voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
