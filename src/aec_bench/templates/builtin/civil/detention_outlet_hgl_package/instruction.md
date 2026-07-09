You are a civil drainage engineer checking a task-owned synthetic SSC-03 detention, outlet-control, and HGL package for one stormwater design event.

Use only the task-owned synthetic source pack values shown below for numeric grading. External EPA SWMM, FHWA HEC-22, and HEC-HMS routes shape the workflow context only; they are not extra data sources for this instance.

## Scene

- Drainage case: `CASE-SSC03-DET-001`
- Catchment table: `CATCH-03-DET-01`
- Rainfall event: `RAIN-03-IDF-10YR`
- Detention basin: `DET-03-BASIN-01`
- Low-flow outlet: `OUT-03-ORIFICE-01`
- Emergency overflow: `OUT-03-WEIR-01`
- Downstream HGL check: `HGL-03-OUTLET-01`
- Report-output trace placeholder: `REPORT-03-SWMMTRACE-01`
- Drainage memo: `MEMO-03-DRAINAGE-01`

## Hydrology And Storage Basis

| Item | Value |
|------|-------|
| Catchment area | {{ catchment_area_ha }} ha |
| Runoff coefficient | {{ runoff_coefficient }} |
| Base rainfall intensity | {{ rainfall_intensity_mm_h }} mm/h |
| Climate factor | {{ climate_factor }} |
| Allowable release rate | {{ allowable_release_rate_m3_s }} m3/s |
| Storm duration | {{ storm_duration_hr }} h |
| DET-03-BASIN-01 bottom storage area | {{ storage_bottom_area_m2 }} m2 |
| DET-03-BASIN-01 top storage area | {{ storage_top_area_m2 }} m2 |
| Active storage depth | {{ active_storage_depth_m }} m |

Hydrology and storage checks:

- Adjusted rainfall intensity equals `rainfall_intensity_mm_h x climate_factor`.
- Rational Method post-development peak flow equals `runoff_coefficient x adjusted_rainfall_intensity_mm_h x catchment_area_ha / 360` in m3/s.
- Required storage uses the simplified triangular hydrograph method from the source pack.
- If `allowable_release_rate_m3_s < post_development_peak_flow_m3_s / 2`, required storage equals `storm_duration_hr x 3600 x (post_development_peak_flow_m3_s / 2 - allowable_release_rate_m3_s)`.
- If `allowable_release_rate_m3_s` is at least half the peak but less than the peak, required storage equals `(post_development_peak_flow_m3_s - allowable_release_rate_m3_s)^2 x storm_duration_hr x 3600 / (2 x post_development_peak_flow_m3_s)`.
- Available storage equals `(bottom_area + top_area) / 2 x active_storage_depth_m`.
- Storage volume margin equals available storage minus required storage.

## Outlet, Freeboard, And HGL Basis

| Item | Value |
|------|-------|
| OUT-03-ORIFICE-01 diameter | {{ orifice_diameter_mm }} mm |
| Orifice discharge coefficient | {{ orifice_discharge_coefficient }} |
| Orifice head | {{ orifice_head_m }} m |
| Major event peak flow | {{ major_event_peak_flow_m3_s }} m3/s |
| OUT-03-WEIR-01 length | {{ emergency_weir_length_m }} m |
| Emergency weir head | {{ emergency_weir_head_m }} m |
| Weir discharge coefficient | {{ weir_discharge_coefficient }} |
| Basin bottom elevation | {{ basin_bottom_elevation_m }} m |
| Embankment crest elevation | {{ embankment_crest_elevation_m }} m |
| Minimum freeboard | {{ minimum_freeboard_m }} m |
| Downstream tailwater elevation | {{ downstream_tailwater_elevation_m }} m |
| Outlet loss | {{ outlet_loss_m }} m |
| Downstream rim elevation | {{ downstream_rim_elevation_m }} m |

Outlet, freeboard, and HGL checks:

- Orifice area equals `pi x diameter_m^2 / 4`.
- Orifice velocity equals `sqrt(2 x 9.81 x orifice_head_m)`.
- Controlled orifice release equals `orifice_discharge_coefficient x orifice_area_m2 x orifice_velocity_m_s`.
- Outlet release margin equals allowable release rate minus controlled orifice release.
- Emergency weir coefficient equals `weir_discharge_coefficient x sqrt(2 x 9.81)`.
- Emergency weir release equals `weir_coefficient x emergency_weir_length_m x emergency_weir_head_m^1.5`.
- Major event excess flow equals major event peak flow minus controlled orifice release.
- Emergency weir margin equals emergency weir release minus major event excess flow.
- Design water surface elevation equals basin bottom elevation plus active storage depth.
- Basin freeboard equals embankment crest elevation minus design water surface elevation.
- Freeboard margin equals basin freeboard minus minimum freeboard.
- Downstream HGL equals downstream tailwater elevation plus outlet loss.
- HGL clearance equals downstream rim elevation minus downstream HGL.
- Overall pass score is `1.0` only when storage margin, outlet release margin, emergency weir margin, freeboard margin, and HGL clearance are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated SWMM report-output evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "adjusted_rainfall_intensity_mm_h": <numeric_value>,
  "post_development_peak_flow_m3_s": <numeric_value>,
  "required_storage_volume_m3": <numeric_value>,
  "available_storage_volume_m3": <numeric_value>,
  "storage_volume_margin_m3": <numeric_value>,
  "orifice_area_m2": <numeric_value>,
  "controlled_orifice_release_m3_s": <numeric_value>,
  "outlet_release_margin_m3_s": <numeric_value>,
  "emergency_weir_release_m3_s": <numeric_value>,
  "major_event_excess_flow_m3_s": <numeric_value>,
  "emergency_weir_margin_m3_s": <numeric_value>,
  "design_water_surface_elevation_m": <numeric_value>,
  "basin_freeboard_m": <numeric_value>,
  "freeboard_margin_m": <numeric_value>,
  "downstream_hgl_m": <numeric_value>,
  "hgl_clearance_m": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
