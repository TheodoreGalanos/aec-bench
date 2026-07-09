You are a civil/coastal engineer checking a task-owned synthetic SSC-04 coastal erosion, longshore transport, and temporary works package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External longshore-transport, shoreline monitoring, sediment-control, and temporary-works workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-04-LH-05`
- Beach profile: `BEACH-04-PROFILE-05`
- Sediment grading note: `SEDIMENT-04-GRADING-05`
- Wave climate table: `WAVE-04-CLIMATE-05`
- Temporary works schedule: `TEMP-04-WORKS-05`
- Monitoring and permit table: `MONITOR-04-PERMIT-05`
- Coastal erosion memo: `MEMO-04-EROSION-05`

## Source Values

| Item | Value |
|------|-------|
| Transport coefficient | {{ transport_coefficient }} |
| Wave energy factor | {{ wave_energy_factor }} |
| Breaking wave angle | {{ breaking_wave_angle_deg }} deg |
| Exposure days | {{ exposure_days }} days |
| Capture factor | {{ capture_factor }} |
| Selected protection volume | {{ selected_protection_volume_m3 }} m3 |
| Disturbed area | {{ disturbed_area_ha }} ha |
| Design rainfall | {{ design_rainfall_mm }} mm |
| Runoff coefficient | {{ runoff_coefficient }} |
| Selected sediment basin volume | {{ selected_sediment_basin_volume_m3 }} m3 |
| Permitted discharge | {{ permitted_discharge_m3_s }} m3/s |
| Pumped discharge | {{ pumped_discharge_m3_s }} m3/s |
| Monitoring stations installed | {{ monitoring_stations_installed }} |
| Required monitoring stations | {{ required_monitoring_stations }} |
| Allowable alignment offset | {{ allowable_alignment_offset_m }} m |
| Measured alignment offset | {{ measured_alignment_offset_m }} m |

## Checks

- Longshore transport equals transport coefficient times wave energy factor times `sin(2 x breaking wave angle)`.
- Temporary protection volume equals longshore transport times exposure days times capture factor.
- Protection volume margin equals selected protection volume minus temporary protection volume.
- Sediment basin required volume equals disturbed area times design rainfall times runoff coefficient times 10.
- Sediment basin margin equals selected basin volume minus required basin volume.
- Discharge capacity margin equals permitted discharge minus pumped discharge.
- Monitoring coverage fraction equals installed monitoring stations divided by required stations.
- Construction tolerance margin equals allowable alignment offset minus measured alignment offset.
- Overall pass score is `1.0` only when protection, sediment, discharge, monitoring, and tolerance checks pass; otherwise it is `0.0`.

## Output Format

Write a compact temporary works memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "longshore_transport_m3_day": <numeric_value>,
  "temporary_protection_volume_m3": <numeric_value>,
  "protection_volume_margin_m3": <numeric_value>,
  "sediment_basin_required_m3": <numeric_value>,
  "sediment_basin_margin_m3": <numeric_value>,
  "discharge_capacity_margin_m3_s": <numeric_value>,
  "monitoring_coverage_fraction": <numeric_value>,
  "construction_tolerance_margin_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
