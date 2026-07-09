You are an ITS/VMS engineer checking a task-owned synthetic SSC-13 message legibility and power package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External MUTCD, owner message policy, NTCIP, and power tools shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-13-LH-05`
- VMS schedule: `VMS-13-SCHED-05`
- Message library: `MSG-13-LIB-05`
- Road speed and geometry: `ROAD-13-SPEED-05`
- Network topology: `NET-13-TOPO-05`
- Power schedule: `PWR-13-SCHED-05`
- VMS operations memo: `MEMO-13-VMS-05`

All checks use the same sign identity, message library, viewing-speed case, network path, and power schedule.

## Source Values

| Item | Value |
|------|-------|
| Letter height | {{ letter_height_mm }} mm |
| Legibility factor | {{ legibility_factor_m_per_mm }} m/mm |
| Available viewing distance | {{ available_viewing_distance_m }} m |
| Road speed | {{ road_speed_kmh }} km/h |
| Required read time | {{ required_read_time_s }} s |
| Display/controller/modem power | {{ display_power_w }} W / {{ controller_power_w }} W / {{ modem_power_w }} W |
| Circuit capacity | {{ circuit_capacity_w }} W |
| VMS/controller network load | {{ vms_network_mbps }} Mbps / {{ controller_network_mbps }} Mbps |
| Network capacity | {{ network_capacity_mbps }} Mbps |
| Compliant message rows | {{ compliant_message_count }} of {{ required_message_count }} |

## Output Format

Write a compact VMS operations memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "required_legibility_distance_m": <numeric_value>,
  "legibility_distance_margin_m": <numeric_value>,
  "available_read_time_s": <numeric_value>,
  "read_time_margin_s": <numeric_value>,
  "vms_power_load_w": <numeric_value>,
  "power_headroom_w": <numeric_value>,
  "network_load_mbps": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "message_policy_match_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
