You are a fire protection and electrical interface engineer checking a task-owned synthetic SSC-19 fire pump fuel, power, and control resilience package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Fire pump selection, emergency fuel, controller power, feeder sizing, and water-supply workflows shape the context only; this instance does not run pump selection software, parse a real curve, validate a code clause, or prove authority approval.

## Scene

- Product: `SSC-19-LH-06`
- Pump curve: `PUMP-19-CURVE-06`
- Motor and fuel data: `MOTOR-19-FUEL-06`
- Controller load schedule: `CTRL-19-LOAD-06`
- Supply curve: `SUPPLY-19-CURVE-06`
- Authority criteria: `CRIT-19-AUTH-06`
- Pump resilience memo: `MEMO-19-PUMP-06`

## Source Values

| Item | Value |
| --- | --- |
| Pump flow | {{ pump_flow_gpm }} gpm |
| Pump head | {{ pump_head_psi }} psi |
| Pump efficiency | {{ pump_efficiency }} |
| Motor efficiency | {{ motor_efficiency }} |
| Selected motor | {{ selected_motor_hp }} hp |
| Fuel rate | {{ fuel_rate_gal_h }} gal/h |
| Required runtime | {{ required_runtime_h }} h |
| Fuel tank | {{ fuel_tank_gal }} gal |
| Controller load | {{ controller_load_kw }} kW |
| Jockey pump control load | {{ jockey_pump_load_kw }} kW |
| Battery voltage | {{ battery_voltage_v }} V |
| Battery capacity | {{ battery_capacity_ah }} Ah |
| Usable battery fraction | {{ usable_battery_fraction }} |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder current | {{ feeder_current_a }} A |
| Feeder length | {{ feeder_length_m }} m |
| Conductor resistance | {{ conductor_resistance_ohm_km }} ohm/km |
| Maximum voltage drop | {{ max_voltage_drop_percent }} % |
| Available fire flow | {{ available_fire_flow_gpm }} gpm |
| Required fire flow | {{ required_fire_flow_gpm }} gpm |

## Checks

- Water horsepower equals pump flow times pump head divided by 1714.
- Brake horsepower equals water horsepower divided by pump efficiency.
- Motor input horsepower equals brake horsepower divided by motor efficiency.
- Fuel required equals fuel rate times required runtime.
- Control energy equals controller plus jockey load times required runtime.
- Battery energy equals voltage times capacity times usable fraction divided by 1000.
- Three-phase feeder voltage drop follows `sqrt(3) x current x length x resistance / 1000 / voltage x 100`.
- Overall pass score is `1.0` only when motor, fuel, battery, voltage-drop, and flow margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "water_horsepower_hp": <numeric_value>,
  "brake_horsepower_hp": <numeric_value>,
  "motor_input_hp": <numeric_value>,
  "motor_margin_hp": <numeric_value>,
  "fuel_required_gal": <numeric_value>,
  "fuel_margin_gal": <numeric_value>,
  "control_energy_required_kwh": <numeric_value>,
  "battery_energy_available_kwh": <numeric_value>,
  "battery_energy_margin_kwh": <numeric_value>,
  "feeder_voltage_drop_percent": <numeric_value>,
  "voltage_drop_margin_percent": <numeric_value>,
  "fire_flow_margin_gpm": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
