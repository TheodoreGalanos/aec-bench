You are an ITS and emergency traffic operations engineer checking a task-owned synthetic SSC-01 detour device continuity package.

Use only the task-owned synthetic source pack values below for numeric grading. MUTCD detour practice, ITS network design, RF link-budget workflows, and roadside power checks shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-01-LH-04`
- Detour plan: `DETOUR-SSC01-004`
- Device inventory: `DEV-SSC01-004`
- RF link sheet: `RF-SSC01-004`
- Power topology: `PWR-SSC01-004`
- Operations memo: `MEMO-SSC01-004`
- Selected message: `DETOUR USE RAMP B`

## Source Values

- VMS character height: {{ vms_character_height_in }} in
- Detour speed: {{ detour_speed_kmh }} km/h
- Reading rate: {{ reading_rate_chars_s }} chars/s
- Message length: {{ detour_message_length_chars }} chars
- CCTV count and load: {{ cctv_count }} at {{ cctv_load_mbps }} Mbps
- VMS count and load: {{ vms_count }} at {{ vms_load_mbps }} Mbps
- Radio and controller load: {{ radio_load_mbps }} Mbps and {{ controller_load_mbps }} Mbps
- Network overhead and uplink: {{ network_overhead_pct }} % and {{ uplink_capacity_mbps }} Mbps
- RF transmit power, gains, path loss, misc loss, fade margin, and sensitivity: {{ rf_tx_power_dbm }} dBm, {{ rf_tx_gain_db }} dB, {{ rf_rx_gain_db }} dB, {{ rf_path_loss_db }} dB, {{ rf_misc_loss_db }} dB, {{ rf_fade_margin_db }} dB, {{ rf_receiver_sensitivity_dbm }} dBm
- Battery capacity and efficiency: {{ battery_capacity_kwh }} kWh and {{ battery_efficiency }}
- Critical load and required duration: {{ critical_load_w }} W and {{ required_detour_duration_h }} h
- Feeder length, resistance, voltage, power factor, and voltage-drop limit: {{ feeder_length_km }} km, {{ conductor_resistance_ohm_km }} ohm/km, {{ feeder_voltage_v }} V, {{ power_factor }}, {{ allowable_voltage_drop_pct }} %

## Required Calculations

- VMS reading time is character height times 40 ft/in, converted to metres, divided by detour speed.
- Message margin is readable characters minus selected message length.
- Required network load is base device load times the overhead factor.
- RF received power is transmit power plus gains minus path, miscellaneous, and fade losses.
- RF link margin is received power minus receiver sensitivity.
- Battery runtime is `capacity x efficiency / (critical load / 1000)`.
- Feeder voltage drop is `2 x length x resistance x current / voltage x 100`.
- Overall pass score is `1.0` only when VMS, network, RF, battery, and voltage-drop margins pass.

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state that the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "vms_reading_time_s": <numeric_value>,
  "vms_message_margin_chars": <numeric_value>,
  "required_network_mbps": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "rf_received_power_dbm": <numeric_value>,
  "rf_link_margin_db": <numeric_value>,
  "battery_runtime_h": <numeric_value>,
  "battery_margin_h": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
