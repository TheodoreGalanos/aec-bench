You are an electrical/security engineer checking a task-owned synthetic SSC-08 crowd, CCTV, and communications operations package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External queue, CCTV coverage, video retention, communications, PoE, and access-control workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-08-LH-04`
- Population and queue schedule: `QUEUE-08-SCHED-04`
- Camera layout: `CCTV-08-LAYOUT-04`
- Network topology: `NET-08-TOPO-04`
- PoE switch schedule: `POE-08-SWITCH-04`
- Access-control state table: `ACCESS-08-STATE-04`
- Security operations memo: `MEMO-08-SECURITY-04`

## Source Values

| Item | Value |
|------|-------|
| Queue length | {{ queue_length_m }} m |
| Queue width | {{ queue_width_m }} m |
| Queue density | {{ queue_density_person_m2 }} persons/m2 |
| Horizontal pixels | {{ horizontal_pixels }} px |
| Camera horizontal field | {{ camera_horizontal_field_m }} m |
| Required PPM | {{ required_ppm }} |
| Camera count | {{ camera_count }} |
| Camera bitrate | {{ camera_bitrate_mbps }} Mbps |
| Retention days | {{ retention_days }} days |
| Storage overhead factor | {{ storage_overhead_factor }} |
| Access network load | {{ access_network_mbps }} Mbps |
| Intercom network load | {{ intercom_network_mbps }} Mbps |
| Network overhead | {{ network_overhead_percent }} percent |
| Uplink capacity | {{ uplink_capacity_mbps }} Mbps |
| Camera PoE load | {{ camera_poe_w }} W |
| Access controller count | {{ access_controller_count }} |
| Access controller PoE load | {{ access_controller_poe_w }} W |
| Intercom count | {{ intercom_count }} |
| Intercom PoE load | {{ intercom_poe_w }} W |
| PoE budget | {{ poe_budget_w }} W |
| Matching access states | {{ matching_access_states }} |
| Required access states | {{ required_access_states }} |

## Checks

- Queue population equals queue length times queue width times queue density.
- CCTV pixels per metre equals horizontal pixels divided by camera horizontal field.
- PPM margin equals CCTV PPM minus required PPM.
- CCTV storage equals total bitrate times retention duration, converted to decimal TB, times storage overhead factor.
- Network load equals CCTV, access, and intercom load with network overhead.
- Network headroom equals uplink capacity minus network load.
- PoE load equals camera, access-controller, and intercom PoE loads.
- Access-state match fraction equals matching access states divided by required states.
- Overall pass score is `1.0` only when PPM, network, PoE, and access-state checks pass; otherwise it is `0.0`.

## Output Format

Write a compact security operations memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "queue_population_persons": <numeric_value>,
  "cctv_pixels_per_m": <numeric_value>,
  "ppm_margin": <numeric_value>,
  "cctv_storage_tb": <numeric_value>,
  "network_load_mbps": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "poe_load_w": <numeric_value>,
  "poe_headroom_w": <numeric_value>,
  "access_state_match_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
