You are a road visual operations engineer checking a task-owned synthetic SSC-13 package for lighting, ITS, CCTV, communications, and field power handoffs.

Use only the task-owned synthetic source pack values shown below for numeric grading. External AGi32, DIALux, MUTCD, Axis/JVSG, ARC-IT, and NTCIP routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Road segment: `RD-SSC13-001`
- Scenario: `NIGHT-INCIDENT-01`
- Cabinet: `CAB-01`
- Variable message sign: `VMS-01`
- PoE switch: `SW-01`
- Fibre uplink: `FIB-01`
- VMS policy: `MSG-POL-01`
- Allowed VMS messages: `INCIDENT AHEAD - MERGE RIGHT` and `REDUCE SPEED - QUEUE AHEAD`

## Lighting Grid

| Grid ID | Chainage | Lane | Illuminance |
|---------|----------|------|--------------|
| LG-01 | 15 m | near lane | {{ lighting_grid_lg01_lux }} lux |
| LG-02 | 15 m | far lane | {{ lighting_grid_lg02_lux }} lux |
| LG-03 | 45 m | near lane | {{ lighting_grid_lg03_lux }} lux |
| LG-04 | 45 m | far lane | {{ lighting_grid_lg04_lux }} lux |
| LG-05 | 75 m | near lane | {{ lighting_grid_lg05_lux }} lux |
| LG-06 | 75 m | far lane | {{ lighting_grid_lg06_lux }} lux |
| LG-07 | 105 m | near lane | {{ lighting_grid_lg07_lux }} lux |
| LG-08 | 105 m | far lane | {{ lighting_grid_lg08_lux }} lux |

Lighting checks:

- Average illuminance is the average of the eight grid rows.
- Minimum illuminance is the smallest grid-row value.
- Uniformity is minimum illuminance divided by average illuminance.

## CCTV

| Camera | Target zone | Target width | Horizontal pixels | Bitrate | Retention | Storage overhead |
|--------|-------------|--------------|-------------------|---------|-----------|------------------|
| CCTV-01 | west approach | {{ cctv_01_target_width_m }} m | {{ cctv_01_horizontal_pixels }} px | {{ cctv_01_bitrate_mbps }} Mbps | {{ retention_days }} days | {{ storage_overhead_factor }} |
| CCTV-02 | VMS zone | {{ cctv_02_target_width_m }} m | {{ cctv_02_horizontal_pixels }} px | {{ cctv_02_bitrate_mbps }} Mbps | {{ retention_days }} days | {{ storage_overhead_factor }} |

CCTV checks:

- Pixels per metre equals horizontal pixels divided by target width.
- Storage uses `bitrate_mbps x 24 x 3600 / 8 / 1000` GB per day, multiplied by retention days and storage overhead, then divided by 1000 for TB.

## Network, PoE, Fibre, And UPS

| Item | Network load | PoE load |
|------|--------------|----------|
| CCTV-01 | {{ cctv_01_network_load_mbps }} Mbps | {{ cctv_01_poe_load_w }} W |
| CCTV-02 | {{ cctv_02_network_load_mbps }} Mbps | {{ cctv_02_poe_load_w }} W |
| VMS-01 | {{ vms_network_load_mbps }} Mbps | {{ vms_poe_load_w }} W |
| ENV-01 | {{ environment_sensor_network_load_mbps }} Mbps | {{ environment_sensor_poe_load_w }} W |
| CAB-01 aux telemetry | {{ cabinet_aux_network_load_mbps }} Mbps | 0 W |
| SW-01 PoE budget | - | {{ poe_budget_w }} W |

Fibre check:

- FIB-01 length is {{ fibre_length_km }} km.
- Fibre attenuation is {{ fibre_loss_db_per_km }} dB/km.
- Connector, splice, and reserve losses are {{ connector_loss_db }} dB, {{ splice_loss_db }} dB, and {{ fibre_reserve_loss_db }} dB.
- Optical loss budget is {{ fibre_budget_db }} dB.

UPS selected operating case:

- Lighting load is four luminaires at {{ luminaire_01_power_w }} W, {{ luminaire_02_power_w }} W, {{ luminaire_03_power_w }} W, and {{ luminaire_04_power_w }} W.
- VMS selected load is {{ vms_power_w }} W.
- Cabinet auxiliary load is {{ cabinet_aux_power_w }} W.
- Autonomy is {{ ups_autonomy_h }} h.
- Efficiency is {{ ups_efficiency }}.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state that the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "average_illuminance_lux": <numeric_value>,
  "minimum_illuminance_lux": <numeric_value>,
  "uniformity_ratio": <numeric_value>,
  "cctv_01_pixels_per_meter": <numeric_value>,
  "cctv_02_pixels_per_meter": <numeric_value>,
  "cctv_01_storage_tb": <numeric_value>,
  "cctv_02_storage_tb": <numeric_value>,
  "total_cctv_storage_tb": <numeric_value>,
  "total_network_load_mbps": <numeric_value>,
  "poe_load_w": <numeric_value>,
  "poe_headroom_w": <numeric_value>,
  "fibre_loss_db": <numeric_value>,
  "fibre_margin_db": <numeric_value>,
  "ups_energy_kwh": <numeric_value>
}
```
