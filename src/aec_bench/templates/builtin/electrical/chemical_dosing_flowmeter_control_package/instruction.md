You are checking `SSC-18-LH-05`, a task-owned synthetic chemical dosing flowmeter and control package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Chemical dosing, flowmeter, pump, valve, loop range, and alarm workflows shape the context only; this instance does not parse a real dosing design basis, vendor export, calibration sheet, or authority-approved control narrative.

Source pack:

- Chemical dosing basis: `DOSE-18-BASIS-05`
- Flowmeter datasheet: `FLOW-18-DATA-05`
- Pump/valve schedule: `PUMP-18-SCHED-05`
- Loop range table: `RANGE-18-LOOP-05`
- Alarm setpoint note: `ALM-18-DOSE-05`
- Dosing control memo: `MEMO-18-DOSE-05`

Given values:

| Field | Value |
| --- | ---: |
| Plant flow | {{ plant_flow_m3_d }} m3/d |
| Dose | {{ dose_mg_l }} mg/L |
| Active fraction | {{ active_fraction }} |
| Solution density | {{ solution_density_kg_l }} kg/L |
| Pump operating hours | {{ pump_operating_hours_d }} h/d |
| Selected pump capacity | {{ selected_pump_capacity_l_h }} L/h |
| Flowmeter range | {{ flowmeter_lower_l_h }} to {{ flowmeter_upper_l_h }} L/h |
| High alarm flow | {{ high_alarm_flow_l_h }} L/h |
| Pump power | {{ pump_power_kw }} kW |
| Supply voltage / power factor | {{ supply_voltage_v }} V / {{ motor_power_factor }} |

Required calculations:

- Active dose mass equals plant flow in litres per day times dose divided by 1,000,000.
- Solution volume equals active dose mass divided by active fraction and solution density.
- Dosing pump flow equals solution volume divided by pump operating hours.
- 4-20 mA flowmeter signal equals `4 + 16 x (flow - lower range) / span`.
- Pump current uses three-phase `P / (sqrt(3) x V x pf)`.

Return one JSON object with keys:

```json
{
  "active_dose_kg_d": <numeric_value>,
  "solution_volume_l_d": <numeric_value>,
  "dosing_pump_flow_l_h": <numeric_value>,
  "pump_capacity_margin_l_h": <numeric_value>,
  "flowmeter_signal_ma": <numeric_value>,
  "high_alarm_current_ma": <numeric_value>,
  "alarm_headroom_ma": <numeric_value>,
  "pump_current_a": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```

Do not claim authority approval, accepted project evidence, dosing-system acceptance, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.
