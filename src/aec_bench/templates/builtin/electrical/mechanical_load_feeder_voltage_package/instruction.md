You are an electrical design engineer checking a task-owned synthetic SSC-05 mechanical-load feeder, power-factor, ampacity, breaker, and voltage-drop package.

Use only the task-owned synthetic source pack values shown below for numeric grading. ETAP, EasyPower, SKM PowerTools, and AS/NZS 3008.1.1-style workflows shape the context only; this instance does not run those tools or parse a real one-line, cable schedule, protection curve, or load-flow export.

## Scene

- Feeder design case: `CASE-SSC05-FEEDER-001`
- Mechanical load schedule: `LOAD-05-MECH-SCHED-01`
- Load calculation table: `LOAD-05-CALC-01`
- Single-line diagram: `SLD-05-MCC-01`
- Upstream switchboard: `SWBD-05-MSB-01`
- Mechanical control centre: `MCC-05`
- Feeder: `FEEDER-05-MCC-01`
- Cable schedule row: `CABLE-05-FDR-01`
- Protective device row: `PROT-05-BKR-01`
- Voltage-drop criterion: `CRIT-05-VDROP-01`
- Electrical design memo: `MEMO-05-ELEC-LOAD-01`

## Mechanical Load And Power-Factor Basis

| Item | Value |
|------|-------|
| Chilled-water pump motor rating | {{ pump_motor_kw }} kW |
| Chilled-water pump quantity | {{ pump_quantity }} |
| Chilled-water pump demand factor | {{ pump_demand_factor }} |
| AHU motor rating | {{ ahu_motor_kw }} kW |
| AHU quantity | {{ ahu_quantity }} |
| AHU demand factor | {{ ahu_demand_factor }} |
| Dosing pump motor rating | {{ dosing_pump_kw }} kW |
| Dosing pump quantity | {{ dosing_quantity }} |
| Dosing pump demand factor | {{ dosing_demand_factor }} |
| Future allowance | {{ future_allowance_pct }} % |
| Initial power factor | {{ initial_power_factor }} |
| Target power factor | {{ target_power_factor }} |
| Selected capacitor bank | {{ selected_capacitor_kvar }} kVAr |

Load and power-factor checks:

- Connected load equals the sum of each equipment rating times its quantity.
- Demand load equals each connected equipment load times its source-owned demand factor, summed across the schedule.
- Future allowance equals `demand_load_kw x future_allowance_pct / 100`.
- Design load equals demand load plus future allowance.
- Initial reactive power equals `design_load_kw x tan(acos(initial_power_factor))`.
- Target reactive power equals `design_load_kw x tan(acos(target_power_factor))`.
- Required capacitor kVAr equals initial reactive power minus target reactive power.
- Selected capacitor margin equals selected capacitor bank minus required capacitor kVAr.
- Corrected apparent power equals `design_load_kw / target_power_factor`.

## Feeder, Cable, Breaker, And Voltage-Drop Basis

| Item | Value |
|------|-------|
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder length | {{ feeder_length_m }} m |
| Voltage-drop factor | {{ feeder_voltage_drop_mv_per_a_m }} mV/A/m |
| Base cable ampacity | {{ base_cable_ampacity_a }} A |
| Ambient derating factor | {{ ambient_derating_factor }} |
| Grouping derating factor | {{ grouping_derating_factor }} |
| Installation derating factor | {{ installation_derating_factor }} |
| Breaker trip rating | {{ breaker_trip_a }} A |
| Breaker continuous factor | {{ breaker_continuous_factor }} |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |

Feeder checks:

- Feeder current equals `corrected_apparent_power_kva x 1000 / (sqrt(3) x feeder_voltage_v)`.
- Derated cable ampacity equals `base_cable_ampacity_a x ambient_derating_factor x grouping_derating_factor x installation_derating_factor`.
- Ampacity margin equals derated cable ampacity minus feeder current.
- Breaker allowable current equals `breaker_trip_a x breaker_continuous_factor`.
- Breaker margin equals breaker allowable current minus feeder current.
- Voltage drop in volts equals `feeder_voltage_drop_mv_per_a_m x feeder_current_a x feeder_length_m / 1000`.
- Feeder voltage drop percent equals `voltage_drop_v / feeder_voltage_v x 100`.
- Voltage-drop margin equals maximum voltage drop percent minus feeder voltage drop percent.
- Overall pass score is `1.0` only when selected capacitor margin, ampacity margin, breaker margin, and voltage-drop margin are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated ETAP/EasyPower/SKM evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "connected_load_kw": <numeric_value>,
  "demand_load_kw": <numeric_value>,
  "future_allowance_kw": <numeric_value>,
  "design_load_kw": <numeric_value>,
  "initial_reactive_power_kvar": <numeric_value>,
  "required_capacitor_kvar": <numeric_value>,
  "selected_capacitor_margin_kvar": <numeric_value>,
  "corrected_apparent_power_kva": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "derated_cable_ampacity_a": <numeric_value>,
  "ampacity_margin_a": <numeric_value>,
  "breaker_allowable_current_a": <numeric_value>,
  "breaker_margin_a": <numeric_value>,
  "voltage_drop_v": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
