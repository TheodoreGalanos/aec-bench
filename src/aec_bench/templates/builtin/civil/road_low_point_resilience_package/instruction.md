You are a road corridor drainage and ITS resilience engineer checking a task-owned synthetic SSC-01 low-point package.

Use only the task-owned synthetic source pack values shown below for numeric grading. FHWA HEC-22, MUTCD, EPA SWMM, Civil 3D, OpenRoads, and InfoDrainage-style routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Road segment: `RD-SSC01-001`
- Low point: `LP-01`
- Drainage catchment: `DRN-CAT-01`
- Upstream bypass record: `DRN-BYP-01`
- Low-point inlet: `DRN-PIT-01`
- Storm-drain reach: `DRN-PIPE-01`
- HGL calculation record: `HGL-01`
- Field cabinet: `CAB-01`
- Variable message sign: `VMS-01`
- Network operating case: `ITS-NET-01`
- Battery schedule: `BATT-01`
- Criteria memo: `CRIT-SSC01-001`
- Selected VMS message: `WATER OVER ROAD - USE LEFT`

## Drainage And Spread

| Item | Value |
|------|-------|
| Runoff coefficient `C` | {{ runoff_coefficient }} |
| Rainfall intensity `I` | {{ rainfall_intensity_mm_h }} mm/h |
| Catchment area `A` | {{ catchment_area_ha }} ha |
| Upstream bypass flow | {{ upstream_bypass_flow_m3_s }} m3/s |
| Cross slope | {{ cross_slope_pct }} % |
| Longitudinal slope | {{ longitudinal_slope_pct }} % |
| Gutter Manning source field | {{ gutter_mannings_n_thousandths }} / 1000 = 0.016 |
| Allowable spread | {{ allowable_spread_m }} m |

Drainage calculations:

- Peak runoff is `Q = C x I x A / 360` in m3/s.
- Gutter approach flow is peak runoff plus upstream bypass flow.
- Use gutter Manning `n = 0.016` exactly.
- Use the triangular-gutter relation `Q = 0.376/n x Sx^(5/3) x SL^(1/2) x T^(8/3)`.
- Solve for spread: `T = (Q x n / (0.376 x Sx^(5/3) x SL^(1/2)))^(3/8)`.
- Convert slopes from percent to m/m before using the formula.
- Curb depth is `T x Sx`.
- Spread margin is allowable spread minus computed spread.

## Inlet, HGL, And Cabinet

| Item | Value |
|------|-------|
| Inlet efficiency | {{ inlet_efficiency }} |
| Inlet capture capacity | {{ inlet_capture_capacity_m3_s }} m3/s |
| Pipe diameter | {{ pipe_diameter_mm }} mm |
| Pipe length | {{ pipe_length_m }} m |
| Pipe Manning source field | {{ pipe_mannings_n_thousandths }} / 1000 = 0.013 |
| Pit loss coefficient | {{ pit_loss_coefficient }} |
| Tailwater level | {{ tailwater_level_m }} m |
| LP-01 pavement level | {{ road_low_point_level_m }} m |
| CAB-01 pad level | {{ cabinet_pad_level_m }} m |
| Minimum HGL clearance | {{ minimum_hgl_clearance_mm }} mm |
| Minimum cabinet freeboard | {{ minimum_cabinet_freeboard_m }} m |

Inlet and HGL calculations:

- Inlet intercepted flow is the lesser of `gutter approach flow x inlet efficiency` and inlet capture capacity.
- Residual ponding flow is approach flow minus intercepted flow, not less than zero.
- Pipe area is `pi x D^2 / 4`, with diameter converted to metres.
- Full-pipe hydraulic radius is `D / 4`.
- Velocity is intercepted flow divided by pipe area.
- Use pipe Manning `n = 0.013` exactly.
- Friction slope is `(V x n / R^(2/3))^2`.
- Friction loss is friction slope times pipe length.
- Pit loss is `K x V^2 / (2g)`.
- Upstream HGL is tailwater level plus friction loss plus pit loss.
- HGL clearance is LP-01 pavement level minus upstream HGL, converted to mm.
- Pavement water level is LP-01 pavement level plus curb depth.
- Controlling water level is the greater of pavement water level and upstream HGL.
- Cabinet freeboard is CAB-01 pad level minus controlling water level.
- Cabinet flood depth is the amount by which controlling water level exceeds CAB-01 pad level, not less than zero.

## VMS, Network, And Battery

| Item | Value |
|------|-------|
| VMS character height | {{ vms_character_height_in }} in |
| Road design speed | {{ road_design_speed_kmh }} km/h |
| Reading rate | {{ reading_rate_chars_s }} chars/s |
| Selected message length | {{ vms_message_length_chars }} chars |
| CCTV cameras | {{ camera_count }} |
| CCTV data rate per camera | {{ camera_data_rate_mbps }} Mbps |
| VMS data rate | {{ vms_data_rate_mbps }} Mbps |
| Controller data rate | {{ controller_data_rate_mbps }} Mbps |
| Water-level sensor data rate | {{ sensor_data_rate_mbps }} Mbps |
| Network overhead | {{ network_overhead_pct }} % |
| Future capacity buffer | {{ future_capacity_buffer_pct }} % |
| Uplink capacity | {{ uplink_capacity_mbps }} Mbps |
| Battery capacity | {{ battery_capacity_kwh }} kWh |
| Battery efficiency | {{ battery_efficiency }} |
| Critical cabinet load | {{ critical_load_w }} W |
| Required autonomy | {{ required_autonomy_h }} h |

VMS, network, and battery calculations:

- VMS legibility distance is character height times 40 ft/in, converted to metres.
- Reading time is legibility distance divided by design speed, with speed converted to m/s.
- Message margin is `reading time x reading rate - selected message length`.
- Base network load is `camera count x camera data rate + VMS data rate + controller data rate + sensor data rate`.
- Required network load is base load times overhead factor times future-buffer factor.
- Network headroom is uplink capacity minus required network load.
- Battery runtime is `battery capacity x battery efficiency / (critical load / 1000)`.
- Battery margin is battery runtime minus required autonomy.
- Overall pass score is `1.0` only when spread margin, HGL clearance, cabinet freeboard, VMS message margin, network headroom, and battery margin all pass the criteria above.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state that the baseline source pack passes the current synthetic checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "peak_runoff_m3_s": <numeric_value>,
  "gutter_approach_flow_m3_s": <numeric_value>,
  "spread_width_m": <numeric_value>,
  "spread_margin_m": <numeric_value>,
  "curb_depth_m": <numeric_value>,
  "inlet_intercepted_flow_m3_s": <numeric_value>,
  "residual_ponding_flow_m3_s": <numeric_value>,
  "hgl_upstream_m": <numeric_value>,
  "hgl_clearance_mm": <numeric_value>,
  "cabinet_freeboard_m": <numeric_value>,
  "cabinet_flood_depth_m": <numeric_value>,
  "vms_reading_time_s": <numeric_value>,
  "vms_message_margin_chars": <numeric_value>,
  "network_headroom_mbps": <numeric_value>,
  "battery_runtime_h": <numeric_value>,
  "battery_margin_h": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
