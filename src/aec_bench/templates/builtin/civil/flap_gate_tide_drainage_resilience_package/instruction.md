You are a civil/coastal drainage engineer checking a task-owned synthetic SSC-04 flap gate, tide, and drainage resilience package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External outfall, flap-gate, HGL, pump-assist, and controls-resilience workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-04-LH-04`
- Outfall section: `OUTFALL-04-SECTION-04`
- Flap gate data: `FLAP-04-DATA-04`
- Tailwater and tide table: `TIDE-04-TAILWATER-04`
- Upstream drainage schedule: `DRAIN-04-UPSTREAM-04`
- Pump/control load note: `PUMP-04-CONTROL-04`
- Drainage resilience memo: `MEMO-04-DRAINAGE-04`

## Source Values

| Item | Value |
|------|-------|
| Pipe diameter | {{ pipe_diameter_m }} m |
| Design flow | {{ design_flow_m3_s }} m3/s |
| Tide level | {{ tide_level_m }} m |
| Surge allowance | {{ surge_allowance_m }} m |
| Outfall invert | {{ outfall_invert_m }} m |
| Flap gate loss coefficient | {{ flap_gate_loss_coefficient }} |
| Pipe friction loss | {{ pipe_friction_loss_m }} m |
| Road low point level | {{ road_low_point_level_m }} m |
| Incoming flow | {{ incoming_flow_m3_s }} m3/s |
| Gravity relief capacity | {{ gravity_relief_capacity_m3_s }} m3/s |
| Tide-locked duration | {{ tide_locked_duration_h }} h |
| Backup storage | {{ backup_storage_m3 }} m3 |
| Pump assist flow | {{ pump_assist_flow_m3_s }} m3/s |
| Pump assist head | {{ pump_assist_head_m }} m |
| Pump efficiency | {{ pump_efficiency }} |
| Control battery capacity | {{ control_battery_capacity_kwh }} kWh |
| Control load | {{ control_load_kw }} kW |
| Required control runtime | {{ required_control_runtime_h }} h |

## Checks

- Pipe area equals `pi x pipe_diameter_m^2 / 4`.
- Outlet velocity equals design flow divided by pipe area.
- Tailwater level equals tide level plus surge allowance.
- Flap gate headloss equals `loss coefficient x velocity^2 / (2 x 9.81)`.
- Upstream HGL equals tailwater level plus flap gate headloss plus pipe friction loss.
- Storage margin equals backup storage minus blocked volume during the tide-locked duration.
- Pump input power equals `1000 x 9.81 x pump flow x head / efficiency / 1000`.
- Control battery margin equals battery capacity minus control load times required runtime.
- Overall pass score is `1.0` only when road HGL, storage, and control battery margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact drainage resilience memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "pipe_area_m2": <numeric_value>,
  "outlet_velocity_m_s": <numeric_value>,
  "tailwater_level_m": <numeric_value>,
  "outfall_submergence_depth_m": <numeric_value>,
  "flap_gate_headloss_m": <numeric_value>,
  "upstream_hgl_m": <numeric_value>,
  "road_low_point_hgl_margin_m": <numeric_value>,
  "storage_margin_m3": <numeric_value>,
  "pump_input_power_kw": <numeric_value>,
  "control_battery_margin_kwh": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
