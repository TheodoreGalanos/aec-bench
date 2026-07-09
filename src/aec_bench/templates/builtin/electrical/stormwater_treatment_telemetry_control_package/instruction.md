You are checking `SSC-18-LH-02`, a task-owned synthetic stormwater or treatment telemetry control package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Telemetry, control narrative, communications, and backup-power workflows shape the context only; this instance does not parse real PLC, SCADA, telemetry, or authority-approved records.

Source pack:

- Sensor schedule: `SENSOR-18-SCHED-02`
- Level/flow table: `LEVEL-18-TABLE-02`
- Control narrative: `NARR-18-CTRL-02`
- Communications topology: `COMMS-18-TOPO-02`
- Power schedule: `PWR-18-SCHED-02`
- Telemetry memo: `MEMO-18-TEL-02`

Given values:

| Field | Value |
| --- | ---: |
| Current level | {{ current_level_m }} m |
| Level range | {{ lower_range_level_m }} to {{ upper_range_level_m }} m |
| High level alarm | {{ high_level_alarm_m }} m |
| Pump start/stop | {{ pump_start_level_m }} / {{ pump_stop_level_m }} m |
| Sensor accuracy | {{ sensor_accuracy_pct_span }} percent of span |
| Telemetry devices | {{ device_count }} at {{ device_power_w }} W |
| Radio power | {{ radio_power_w }} W |
| Backup duration | {{ backup_duration_h }} h |
| Battery | {{ battery_voltage_v }} V, {{ battery_capacity_ah }} Ah, usable fraction {{ battery_usable_fraction }} |
| Inverter efficiency | {{ inverter_efficiency }} |

Required calculations:

- Level span equals upper range minus lower range.
- 4-20 mA signal equals `4 + 16 x (level - lower range) / level span`.
- Sensor accuracy in metres equals level span times accuracy percent divided by 100.
- Telemetry load equals device count times device power plus radio power.
- Backup energy required equals telemetry load times duration divided by inverter efficiency.
- Battery usable energy equals voltage times Ah times usable fraction.

Return one JSON object with keys:

```json
{
  "level_span_m": <numeric_value>,
  "current_signal_ma": <numeric_value>,
  "high_level_current_ma": <numeric_value>,
  "pump_start_current_ma": <numeric_value>,
  "pump_stop_current_ma": <numeric_value>,
  "sensor_accuracy_m": <numeric_value>,
  "pump_start_margin_m": <numeric_value>,
  "telemetry_load_w": <numeric_value>,
  "backup_energy_required_kwh": <numeric_value>,
  "battery_usable_kwh": <numeric_value>,
  "backup_energy_margin_kwh": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```

Do not claim authority approval, accepted project evidence, PLC/SCADA export validity, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.
