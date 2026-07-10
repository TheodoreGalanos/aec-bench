You are a CCTV systems engineer checking a task-owned synthetic SSC-13 coverage, pixel-density, and storage package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External CCTV design and storage tools shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-13-LH-06`
- Camera plan: `CCTV-13-PLAN-06`
- Scene target list: `TARGET-13-LIST-06`
- Camera data sheet: `CAM-13-DATA-06`
- Recording policy: `REC-13-POL-06`
- Network/power schedule: `NET-13-PWR-06`
- Surveillance memo: `MEMO-13-CCTV-06`

All checks use the same camera plan, target list, camera data, recording policy, network path, PoE load, and fibre handoff.

## Source Values

| Item | Value |
|------|-------|
| Camera 01 pixels/target width | {{ camera_01_horizontal_pixels }} px / {{ camera_01_target_width_m }} m |
| Camera 02 pixels/target width | {{ camera_02_horizontal_pixels }} px / {{ camera_02_target_width_m }} m |
| Camera 03 pixels/target width | {{ camera_03_horizontal_pixels }} px / {{ camera_03_target_width_m }} m |
| Required PPM | {{ required_ppm }} |
| Covered targets | {{ covered_targets }} of {{ required_targets }} |
| Camera bitrates | {{ camera_01_bitrate_mbps }}, {{ camera_02_bitrate_mbps }}, {{ camera_03_bitrate_mbps }} Mbps |
| Retention and storage overhead | {{ retention_days }} days / {{ storage_overhead_factor }} |
| Network overhead and capacity | {{ network_overhead_factor }} / {{ uplink_capacity_mbps }} Mbps |
| Camera count and PoE | {{ camera_count }} at {{ camera_poe_w }} W plus {{ recorder_aux_poe_w }} W recorder aux |
| PoE budget | {{ poe_budget_w }} W |
| Fibre basis | {{ fibre_length_km }} km at {{ fibre_loss_db_per_km }} dB/km plus {{ connector_loss_db }}, {{ splice_loss_db }}, {{ reserve_loss_db }} dB |
| Fibre budget | {{ fibre_budget_db }} dB |

## Output Format

Write a compact surveillance memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "camera_01_pixels_per_m": <numeric_value>,
  "camera_02_pixels_per_m": <numeric_value>,
  "camera_03_pixels_per_m": <numeric_value>,
  "minimum_pixels_per_m": <numeric_value>,
  "ppm_margin": <numeric_value>,
  "coverage_match_fraction": <numeric_value>,
  "storage_required_tb": <numeric_value>,
  "network_load_mbps": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "poe_load_w": <numeric_value>,
  "poe_headroom_w": <numeric_value>,
  "fibre_margin_db": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
