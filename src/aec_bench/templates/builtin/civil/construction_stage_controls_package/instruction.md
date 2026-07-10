You are a construction staging engineer checking a task-owned synthetic SSC-16 package for environmental controls, temporary traffic control, monitoring communications, and temporary power readiness.

Use only the task-owned synthetic source pack values shown below for numeric grading. External EPA CGP/SWPPP, FHWA MUTCD temporary-traffic-control, SYNCHRO 4D staging, and construction inspection/reporting routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Construction stage: `STG-SSC16-001`
- Work zone: `WZ-16-A`
- Temporary traffic control plan: `TTC-01`
- Erosion and sediment control plan: `ESCP-01`
- Sediment basin: `SB-01`
- Monitoring station: `MON-01`
- Temporary power board: `TPB-01`
- Solar/battery unit: `PV-BAT-01`
- Inspection record: `INSP-01`
- Hold point: `HP-ENV-TRAFFIC-01`

## Stormwater And Sediment Basin

| Item | Value |
|------|-------|
| Disturbed catchment area draining to SB-01 | {{ disturbed_area_ac }} acres |
| 2-year, 24-hour design storm depth | {{ design_storm_depth_in }} in |
| Runoff coefficient | {{ runoff_coefficient }} |
| Provided SB-01 basin storage | {{ provided_basin_volume_ft3 }} ft3 |
| Provided basin freeboard | {{ provided_freeboard_ft }} ft |
| Required freeboard | {{ required_freeboard_ft }} ft |
| TSS event mean concentration | {{ tss_event_mean_concentration_mg_l }} mg/L |

Stormwater checks:

- Runoff volume equals `disturbed_area_ac x 43,560 x design_storm_depth_in / 12 x runoff_coefficient`.
- Required basin volume equals the calculated runoff volume for this source pack.
- Basin storage headroom equals provided basin storage minus required basin volume.
- Freeboard margin equals provided freeboard minus required freeboard.
- TSS event load equals `runoff_volume_ft3 x 28.316846592 x TSS_mg_L / 453592.37`.

## Temporary Traffic Control

| Item | Value |
|------|-------|
| Work-zone posted speed | {{ work_zone_speed_mph }} mph |
| Lane shift width | {{ lane_shift_width_ft }} ft |
| Provided TTC-01 taper length | {{ provided_taper_length_ft }} ft |
| Channelizer spacing | {{ channelizer_spacing_ft }} ft |
| Provided channelizer count | {{ provided_channelizer_count }} devices |

Temporary traffic checks:

- For this low-speed TTC source pack, taper length equals `lane_shift_width_ft x work_zone_speed_mph^2 / 60`.
- Taper headroom equals provided taper length minus required taper length.
- Minimum channelizer count equals `ceil(required_taper_length / channelizer_spacing) + 1`.
- Channelizer headroom equals provided channelizer count minus minimum channelizer count.

## Monitoring, Communications, And Temporary Power

| Device | Data load | Power load |
|--------|-----------|------------|
| Work-zone camera CAM-16-01 | {{ camera_data_mbps }} Mbps | {{ work_zone_camera_load_w }} W |
| Turbidity logger TURB-01 | {{ turbidity_logger_data_mbps }} Mbps | {{ turbidity_logger_load_w }} W |
| Weather station WX-01 | {{ weather_station_data_mbps }} Mbps | {{ weather_station_load_w }} W |
| Cellular gateway GW-01 | {{ gateway_data_mbps }} Mbps | {{ cellular_router_load_w }} W |

Temporary power checks:

- Total monitoring data load is the sum of the four device data loads.
- Monitoring load is the sum of the four device power loads.
- Battery autonomy equals `battery_capacity_wh x usable_battery_fraction / monitoring_load_w`.
- Solar daily energy equals `solar_panel_power_w x peak_sun_hours x solar_derate_factor`.
- Solar daily headroom equals solar daily energy minus `monitoring_load_w x 24`.

| Temporary power source | Value |
|------------------------|-------|
| Battery capacity | {{ battery_capacity_wh }} Wh |
| Usable battery fraction | {{ usable_battery_fraction }} |
| Solar panel power | {{ solar_panel_power_w }} W |
| Peak sun hours | {{ peak_sun_hours }} h/day |
| Solar derate factor | {{ solar_derate_factor }} |

## Inspection Readiness

| Item | Value |
|------|-------|
| Inspection interval | {{ inspection_interval_days }} days |
| Days since last inspection | {{ days_since_last_inspection }} days |

Inspection check:

- Inspection days remaining equals inspection interval minus days since last inspection.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state that the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "runoff_volume_ft3": <numeric_value>,
  "required_basin_volume_ft3": <numeric_value>,
  "basin_storage_headroom_ft3": <numeric_value>,
  "freeboard_margin_ft": <numeric_value>,
  "tss_load_lb": <numeric_value>,
  "taper_length_ft": <numeric_value>,
  "taper_headroom_ft": <numeric_value>,
  "minimum_channelizer_count": <numeric_value>,
  "channelizer_headroom_count": <numeric_value>,
  "total_monitoring_data_mbps": <numeric_value>,
  "monitoring_load_w": <numeric_value>,
  "battery_autonomy_h": <numeric_value>,
  "solar_daily_headroom_wh": <numeric_value>,
  "inspection_days_remaining": <numeric_value>
}
```
