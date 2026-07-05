You are an electrical security and lighting reviewer checking a task-owned synthetic SSC-13 station/building package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External lighting, CCTV, access-control, and network tools shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-13-LH-02`
- Floor plan: `PLAN-13-ROOM-02`
- Lighting grid: `LIGHT-13-GRID-02`
- CCTV schedule: `CCTV-13-CAM-02`
- Access-control schedule: `ACCESS-13-CTRL-02`
- Network topology: `NET-13-TOPO-02`
- Security operations memo: `MEMO-13-SECURITY-02`

All checks use the same floor/room scene, lighting grid, camera coverage, access devices, and network topology. Do not change device IDs, room geometry, or coverage zones unless you explicitly flag a source conflict.

## Source Values

| Item | Value |
|------|-------|
| Lighting grid lux values | {{ grid_lux_01 }}, {{ grid_lux_02 }}, {{ grid_lux_03 }}, {{ grid_lux_04 }}, {{ grid_lux_05 }}, {{ grid_lux_06 }} |
| Required illuminance | {{ required_illuminance_lux }} lux |
| CCTV horizontal pixels | {{ cctv_horizontal_pixels }} px |
| CCTV target width | {{ cctv_target_width_m }} m |
| Required PPM | {{ required_ppm }} |
| Camera count | {{ camera_count }} |
| Camera network load | {{ camera_network_mbps }} Mbps each |
| Access network load | {{ access_network_mbps }} Mbps |
| Lighting controller network load | {{ lighting_control_network_mbps }} Mbps |
| Network overhead factor | {{ network_overhead_factor }} |
| Uplink capacity | {{ uplink_capacity_mbps }} Mbps |
| Camera PoE load | {{ camera_poe_w }} W each |
| Access controller count | {{ access_controller_count }} |
| Access controller PoE load | {{ access_controller_poe_w }} W each |
| PoE budget | {{ poe_budget_w }} W |
| Matched coverage zones | {{ matched_coverage_zones }} of {{ required_coverage_zones }} |

## Output Format

Write a compact security operations memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "average_illuminance_lux": <numeric_value>,
  "minimum_illuminance_lux": <numeric_value>,
  "uniformity_ratio": <numeric_value>,
  "illuminance_margin_lux": <numeric_value>,
  "cctv_pixels_per_m": <numeric_value>,
  "cctv_ppm_margin": <numeric_value>,
  "network_load_mbps": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "poe_load_w": <numeric_value>,
  "poe_headroom_w": <numeric_value>,
  "coverage_match_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
