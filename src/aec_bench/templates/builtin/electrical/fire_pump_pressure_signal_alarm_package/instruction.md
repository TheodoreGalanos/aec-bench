You are checking `SSC-18-LH-06`, a task-owned synthetic fire pump pressure signal and alarm package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Fire pump, pressure sensor, alarm threshold, NAC load, and battery workflow context shapes this instance only; it does not parse a real fire pump schematic, alarm panel export, or authority-approved fire design.

Source pack:

- Fire pump schematic: `FIRE-18-PUMP-06`
- Pressure sensor data sheet: `PRESS-18-SENSOR-06`
- Alarm threshold table: `ALM-18-THRESH-06`
- NAC/load schedule: `NAC-18-LOAD-06`
- Fire authority criterion: `CRIT-18-FIRE-06`
- Fire control memo: `MEMO-18-FIRE-06`

Given values:

| Field | Value |
| --- | ---: |
| Residual pressure | {{ residual_pressure_kpa }} kPa |
| Pressure range | {{ pressure_lower_kpa }} to {{ pressure_upper_kpa }} kPa |
| Low alarm pressure | {{ low_alarm_pressure_kpa }} kPa |
| Pump start pressure | {{ pump_start_pressure_kpa }} kPa |
| NAC devices/current | {{ nac_device_count }} at {{ nac_device_current_a }} A |
| NAC panel capacity | {{ nac_panel_capacity_a }} A |
| Control load | {{ control_load_w }} W |
| Standby/alarm duration | {{ standby_duration_h }} / {{ alarm_duration_h }} h |
| Battery capacity | {{ battery_capacity_kwh }} kWh |
| DC voltage / charger efficiency | {{ dc_voltage_v }} V / {{ charger_efficiency }} |

Required calculations:

- 4-20 mA pressure signal equals `4 + 16 x (pressure - lower range) / pressure span`.
- Alarm margins compare residual pressure to the low-alarm and pump-start thresholds.
- NAC load equals device count times device current.
- Battery required energy combines standby control load and alarm NAC load, divided by charger efficiency.

Return one JSON object with keys:

```json
{
  "pressure_signal_ma": <numeric_value>,
  "low_alarm_current_ma": <numeric_value>,
  "pump_start_current_ma": <numeric_value>,
  "low_alarm_margin_kpa": <numeric_value>,
  "pump_start_margin_kpa": <numeric_value>,
  "nac_load_a": <numeric_value>,
  "nac_panel_margin_a": <numeric_value>,
  "battery_required_kwh": <numeric_value>,
  "battery_margin_kwh": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```

Do not claim authority approval, accepted project evidence, fire-system acceptance, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.
