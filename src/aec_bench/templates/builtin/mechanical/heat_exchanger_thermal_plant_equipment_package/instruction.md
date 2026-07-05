You are a thermal plant engineer checking a task-owned synthetic SSC-06 heat exchanger and thermal plant equipment package.

Use only the task-owned synthetic source pack values shown below for numeric grading. LMTD, pump duty, motor, and support handoff workflows shape the context only; this instance does not run external software or parse a real source pack.

## Scene

- Product: `SSC-06-LH-06`
- Process flow/temperature table: `PROCESS-06-THERMAL-06`
- Heat-exchanger data sheet: `HX-06-DATA-06`
- Pump curve: `PUMP-06-CURVE-06`
- Motor schedule: `MOTOR-06-SCHED-06`
- Support layout: `SUPPORT-06-LAYOUT-06`
- Thermal equipment memo: `MEMO-06-THERMAL-06`

## Source Values

| Item | Value |
| --- | --- |
| Hot-side mass flow | {{ hot_flow_kg_s }} kg/s |
| Fluid specific heat | {{ fluid_cp_kj_kg_c }} kJ/kg-C |
| Hot inlet temperature | {{ hot_inlet_c }} C |
| Hot outlet temperature | {{ hot_outlet_c }} C |
| Cold inlet temperature | {{ cold_inlet_c }} C |
| Cold outlet temperature | {{ cold_outlet_c }} C |
| Selected UA | {{ selected_ua_kw_per_c }} kW/C |
| Fluid density | {{ fluid_density_kg_m3 }} kg/m3 |
| Circulation pump head | {{ circulation_pump_head_m }} m |
| Pump efficiency | {{ pump_efficiency }} |
| Motor efficiency | {{ motor_efficiency }} |
| Selected motor size | {{ selected_motor_kw }} kW |
| Heat exchanger mass | {{ heat_exchanger_mass_kg }} kg |
| Pump mass | {{ pump_mass_kg }} kg |
| Support count | {{ support_count }} |

## Calculation Rules

- Heat load equals `hot_flow_kg_s x fluid_cp_kj_kg_c x (hot_inlet_c - hot_outlet_c)`.
- LMTD uses `(delta1 - delta2) / ln(delta1 / delta2)`, or the common delta when the two terminal differences are equal.
- Required UA equals heat load divided by LMTD.
- UA margin equals selected UA minus required UA.
- Process flow equals `hot_flow_kg_s / fluid_density_kg_m3 x 3600`.
- Pump hydraulic power equals `density x 9.81 x flow_m3_s x circulation_pump_head_m / 1000`.
- Pump shaft power equals hydraulic power divided by pump efficiency.
- Motor input power equals pump shaft power divided by motor efficiency.
- Motor margin equals selected motor size minus motor input power.
- Support service reaction equals combined equipment mass times 9.81 divided by support count.
- Overall pass score is `1.0` only when UA and motor margins are non-negative.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated modelling evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "heat_load_kw": <numeric_value>,
  "lmtd_c": <numeric_value>,
  "required_ua_kw_per_c": <numeric_value>,
  "ua_margin_kw_per_c": <numeric_value>,
  "process_flow_m3_h": <numeric_value>,
  "pump_hydraulic_power_kw": <numeric_value>,
  "pump_shaft_power_kw": <numeric_value>,
  "motor_input_power_kw": <numeric_value>,
  "motor_margin_kw": <numeric_value>,
  "support_service_reaction_kn": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
