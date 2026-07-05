You are an electrical and rail systems engineer checking a task-owned synthetic SSC-02 level-crossing warning-time, backup-power, DC feeder, and fiber communications package.

Use only the task-owned synthetic source pack values shown below for numeric grading. 49 CFR Part 234, FHWA MUTCD Part 8, AREMA C&S Manual routes, and operator level-crossing workflows shape the context only; this instance does not run signalling design software, parse real signal plans, verify an authority standard, or prove full rail safety compliance.

## Scene

- Design case: `CASE-SSC02-LX-001`
- Route profile: `ROUTE-02-PROFILE-01`
- Level crossing layout: `LX-02-LAYOUT-01`
- Warning-time worksheet: `WT-02-WARN-01`
- Crossing controller: `CTRL-02-XING-01`
- Signal and communications load schedule: `LOAD-02-SIG-01`
- Battery and UPS datasheet: `BATT-02-UPS-01`
- DC feeder schedule: `FEEDER-02-DC-01`
- Fiber communications link: `FIBER-02-COMMS-01`
- Degraded-mode operating note: `OPS-02-DEGRADED-01`
- Engineering memo: `MEMO-02-LX-OPS-01`

## Warning-Time And Gate Basis

| Item | Value |
|------|-------|
| Controlling approach speed | {{ maximum_train_speed_kmh }} km/h |
| Minimum warning time | {{ minimum_warning_time_s }} s |
| Road-user clearance time | {{ road_user_clearance_time_s }} s |
| Gate lowering time | {{ gate_lowering_time_s }} s |
| System delay | {{ system_delay_s }} s |
| Delay from warning start to gate descent | {{ gate_start_delay_s }} s |
| Required gate-horizontal time before arrival | {{ required_gate_horizontal_before_arrival_s }} s |

Warning checks:

- Maximum train speed in m/s equals `maximum_train_speed_kmh / 3.6`.
- Total warning time equals `minimum_warning_time_s + road_user_clearance_time_s + gate_lowering_time_s + system_delay_s`.
- Strike-in distance equals maximum train speed in m/s times total warning time.
- Minimum warning margin equals total warning time minus minimum warning time.
- Gate-horizontal margin equals total warning time minus gate start delay, gate lowering time, and required gate-horizontal time before arrival.

## Signal Load And Backup-Power Basis

| Item | Value |
|------|-------|
| Crossing controller load | {{ controller_load_w }} W |
| Flashing-light load per assembly | {{ flashing_light_load_w }} W |
| Flashing-light assembly count | {{ flashing_light_count }} |
| Gate mechanism load per mechanism | {{ gate_mechanism_load_w }} W |
| Gate mechanism count | {{ gate_mechanism_count }} |
| Communications switch load | {{ comms_switch_load_w }} W |
| Track circuit and detector load | {{ track_circuit_load_w }} W |
| Event recorder load | {{ event_recorder_load_w }} W |
| Load future allowance | {{ load_future_allowance_pct }} % |
| Required autonomy | {{ required_autonomy_h }} h |
| DC system voltage | {{ dc_system_voltage_v }} V |
| Depth of discharge | {{ depth_of_discharge_pct }} % |
| Temperature derating factor | {{ temperature_derating_factor }} |
| Inverter efficiency | {{ inverter_efficiency_pct }} % |
| Installed battery capacity | {{ installed_battery_capacity_ah }} Ah |
| Battery block voltage | {{ battery_block_voltage_v }} V |
| UPS load power factor | {{ load_power_factor }} |
| Selected UPS rating | {{ selected_ups_rating_va }} VA |

Load and backup-power checks:

- Connected signal load equals controller load, flashing-light load times count, gate-mechanism load times count, communications switch load, track-circuit load, and event-recorder load.
- Design signal load equals connected signal load times `(1 + load_future_allowance_pct / 100)`.
- Required energy equals `design_signal_load_w x required_autonomy_h / 1000`.
- Usable battery fraction equals `depth_of_discharge_pct / 100 x temperature_derating_factor x inverter_efficiency_pct / 100`.
- Required battery capacity equals `design_signal_load_w x required_autonomy_h / (dc_system_voltage_v x usable battery fraction)`.
- Battery capacity margin equals installed battery capacity minus required battery capacity.
- Required UPS rating equals `design_signal_load_w / load_power_factor`.
- UPS rating margin equals selected UPS rating minus required UPS rating.
- Battery block count equals `ceil(dc_system_voltage_v / battery_block_voltage_v)`.

## DC Feeder And Fiber Basis

| Item | Value |
|------|-------|
| DC feeder one-way length | {{ feeder_length_m }} m |
| Feeder resistance | {{ feeder_resistance_milliohm_per_m }} milliohm/m |
| Maximum DC feeder voltage drop | {{ max_voltage_drop_percent }} % |
| Fiber length | {{ fiber_length_km }} km |
| Fiber attenuation | {{ fiber_attenuation_db_per_km }} dB/km |
| Fiber connector count | {{ fiber_connector_count }} |
| Connector loss | {{ connector_loss_db }} dB |
| Fiber splice count | {{ fiber_splice_count }} |
| Splice loss | {{ splice_loss_db }} dB |
| Patch-panel allowance | {{ patch_panel_allowance_db }} dB |
| Optical transmitter power | {{ optical_tx_power_dbm }} dBm |
| Receiver sensitivity | {{ receiver_sensitivity_dbm }} dBm |
| Required fiber margin | {{ required_fiber_margin_db }} dB |

Feeder and fiber checks:

- DC feeder current equals `design_signal_load_w / dc_system_voltage_v`.
- DC feeder voltage drop equals `2 x dc_feeder_current_a x feeder_length_m x feeder_resistance_milliohm_per_m / 1000`.
- DC feeder voltage drop percent equals `dc_feeder_voltage_drop_v / dc_system_voltage_v x 100`.
- DC voltage-drop margin equals maximum voltage drop percent minus DC feeder voltage drop percent.
- Fiber total loss equals fiber length attenuation plus connector, splice, and patch-panel losses.
- Fiber receive power equals optical transmitter power minus fiber total loss.
- Fiber link margin equals fiber receive power minus receiver sensitivity.
- Fiber excess margin equals fiber link margin minus required fiber margin.
- Overall pass score is `1.0` only when minimum warning margin, gate-horizontal margin, battery capacity margin, UPS rating margin, DC voltage-drop margin, and fiber excess margin are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated signalling-software evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "maximum_train_speed_m_s": <numeric_value>,
  "total_warning_time_s": <numeric_value>,
  "strike_in_distance_m": <numeric_value>,
  "minimum_warning_margin_s": <numeric_value>,
  "gate_horizontal_margin_s": <numeric_value>,
  "connected_signal_load_w": <numeric_value>,
  "design_signal_load_w": <numeric_value>,
  "required_energy_kwh": <numeric_value>,
  "required_battery_capacity_ah": <numeric_value>,
  "battery_capacity_margin_ah": <numeric_value>,
  "required_ups_rating_va": <numeric_value>,
  "ups_rating_margin_va": <numeric_value>,
  "battery_block_count": <numeric_value>,
  "dc_feeder_current_a": <numeric_value>,
  "dc_feeder_voltage_drop_v": <numeric_value>,
  "dc_feeder_voltage_drop_percent": <numeric_value>,
  "dc_voltage_drop_margin_percent": <numeric_value>,
  "fiber_total_loss_db": <numeric_value>,
  "fiber_receive_power_dbm": <numeric_value>,
  "fiber_link_margin_db": <numeric_value>,
  "fiber_excess_margin_db": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
