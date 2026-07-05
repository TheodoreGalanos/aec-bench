You are a road lighting and ITS operations engineer checking a task-owned synthetic SSC-01 lighting, device, drainage, and power scene.

Use only the task-owned synthetic source pack values below for numeric grading. AGi32/DIALux-style lighting workflows, MUTCD traffic-device practice, CCTV design tools, and ITS network handoff practice shape the context only; they are not extra data sources for this instance.

## Scene

- Product: `SSC-01-LH-03`
- Road layout: `RD-SSC01-003`
- Lighting grid: `LGT-SSC01-003`
- CCTV and VMS schedule: `CCTV-SSC01-003`
- Network topology: `NET-SSC01-003`
- Cabinet power schedule: `PWR-SSC01-003`
- Operations memo: `MEMO-SSC01-003`

## Source Values

Lighting grid lux values: {{ lighting_lux_01 }}, {{ lighting_lux_02 }}, {{ lighting_lux_03 }}, {{ lighting_lux_04 }}, {{ lighting_lux_05 }}, {{ lighting_lux_06 }}.

Network and storage:

- CCTV count: {{ cctv_count }}
- CCTV network load per camera: {{ cctv_network_load_mbps }} Mbps
- VMS network load: {{ vms_network_load_mbps }} Mbps
- Storm sensor network load: {{ sensor_network_load_mbps }} Mbps
- Controller network load: {{ controller_network_load_mbps }} Mbps
- Network overhead: {{ network_overhead_pct }} %
- Uplink capacity: {{ uplink_capacity_mbps }} Mbps
- Total CCTV bitrate: {{ cctv_total_bitrate_mbps }} Mbps
- Retention: {{ retention_days }} days
- Storage overhead factor: {{ storage_overhead_factor }}

Power and storm operation:

- CCTV PoE load per camera: {{ cctv_poe_load_w }} W
- VMS PoE load: {{ vms_poe_load_w }} W
- Sensor PoE load: {{ sensor_poe_load_w }} W
- PoE budget: {{ poe_budget_w }} W
- Storm sensor level: {{ storm_sensor_level_m }} m
- Storm alarm threshold: {{ storm_alarm_threshold_m }} m
- Luminaire count and power: {{ luminaire_count }} at {{ luminaire_power_w }} W
- Device UPS load: {{ device_ups_load_w }} W
- UPS autonomy: {{ ups_autonomy_h }} h
- UPS efficiency: {{ ups_efficiency }}
- Minimum uniformity ratio: {{ minimum_uniformity_ratio }}

## Required Calculations

- Average illuminance is the arithmetic mean of the six grid values.
- Minimum illuminance is the lowest grid value.
- Uniformity ratio is minimum illuminance divided by average illuminance.
- Glare variation ratio is maximum illuminance divided by average illuminance.
- Total network load is base device load times the overhead factor.
- Network headroom is uplink capacity minus total network load.
- CCTV storage uses decimal units: `bitrate x seconds / 8 / 1000 x days x overhead / 1000`.
- PoE load is camera, VMS, and sensor load; PoE headroom is budget minus load.
- Water-level margin is alarm threshold minus current storm sensor level.
- UPS energy is selected load times autonomy divided by efficiency.
- Overall pass score is `1.0` only when uniformity, network, PoE, and storm-level checks pass.

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state that the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "average_illuminance_lux": <numeric_value>,
  "minimum_illuminance_lux": <numeric_value>,
  "uniformity_ratio": <numeric_value>,
  "glare_variation_ratio": <numeric_value>,
  "total_network_load_mbps": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "total_cctv_storage_tb": <numeric_value>,
  "poe_load_w": <numeric_value>,
  "poe_headroom_w": <numeric_value>,
  "water_level_margin_m": <numeric_value>,
  "ups_energy_kwh": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
