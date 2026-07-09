You are an electrical design engineer checking `SSC-05-LH-04`, a task-owned synthetic SSC-05 fire/life-safety and communications load package.

Use only the task-owned synthetic source pack values below for numeric grading. Fire alarm, access-control, CCTV, communications-topology, and UPS autonomy workflows shape the context only; this instance does not run those tools or parse a real fire alarm schedule, network model, or UPS data export.

## Scene

- Design case: `CASE-SSC05-LIFE-04`
- Fire alarm load schedule: `FIRE-05-LOAD-04`
- Access/CCTV device schedule: `CCTV-05-DEVICE-04`
- Communications topology: `COMMS-05-TOPO-04`
- Battery/UPS data sheet: `UPS-05-DATA-04`
- Emergency operating criterion: `CRIT-05-EMERG-04`
- Life-safety power memo: `MEMO-05-LIFE-04`

## Source Values

| Item | Value |
|------|-------|
| NAC device count | {{ nac_device_count }} |
| NAC device current | {{ nac_device_current_a }} A |
| NAC voltage | {{ nac_voltage_v }} V |
| Fire panel load | {{ fire_panel_load_kw }} kW |
| Emergency lighting load | {{ emergency_lighting_load_kw }} kW |
| Access controller count | {{ access_controller_count }} |
| Access controller load | {{ access_controller_w }} W |
| CCTV camera count | {{ cctv_camera_count }} |
| CCTV camera load | {{ cctv_camera_w }} W |
| Network core load | {{ network_core_w }} W |
| Emergency runtime | {{ emergency_runtime_h }} h |
| UPS nominal energy | {{ ups_nominal_kwh }} kWh |
| UPS usable fraction | {{ ups_usable_fraction }} |
| NAC circuit limit | {{ nac_circuit_limit_a }} A |
| Feeder voltage | {{ feeder_voltage_v }} V |
| Feeder allowable current | {{ feeder_allowable_current_a }} A |

Checks:

- NAC current equals `nac_device_count x nac_device_current_a`.
- Life-safety load equals NAC power plus fire panel load plus emergency lighting load.
- Communications load equals access-controller, CCTV, and network-core loads.
- Battery required equals `total_essential_load_kw x emergency_runtime_h`.
- Usable battery equals `ups_nominal_kwh x ups_usable_fraction`.
- Feeder current equals `total_essential_load_kw x 1000 / feeder_voltage_v`.
- Overall pass score is `1.0` only when battery, NAC, and feeder margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Preserve the object IDs above, state the task-owned synthetic source-pack boundary, and explain whether the baseline source pack passes the docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated software evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "life_safety_load_kw": <numeric_value>,
  "communications_load_kw": <numeric_value>,
  "total_essential_load_kw": <numeric_value>,
  "battery_required_kwh": <numeric_value>,
  "usable_battery_kwh": <numeric_value>,
  "battery_margin_kwh": <numeric_value>,
  "nac_current_a": <numeric_value>,
  "nac_margin_a": <numeric_value>,
  "feeder_current_a": <numeric_value>,
  "feeder_margin_a": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
