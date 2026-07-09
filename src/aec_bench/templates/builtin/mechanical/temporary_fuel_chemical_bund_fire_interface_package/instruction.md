You are a construction site safety engineer checking a task-owned synthetic SSC-16 package for temporary fuel/chemical storage bunding, drainage isolation, fire mode, alarm load, and spill response.

Use only the task-owned synthetic source pack values shown below for numeric grading. External hazardous-material storage, fire interface, alarm load, and construction inspection workflows shape the context only; they are not extra data sources for this instance.

## Source Objects

- Product: `SSC-16-LH-06`
- Storage layout: `STORE-16-LAYOUT-06`
- Fuel/chemical inventory: `INV-16-FUEL-06`
- Bund detail: `BUND-16-DETAIL-06`
- Fire/hazard note: `FIRE-16-NOTE-06`
- Monitoring/alarm load schedule: `ALARM-16-LOAD-06`
- Site safety memo: `MEMO-16-SAFETY-06`

## Source Values

| Item | Value |
|------|-------|
| Largest container | {{ largest_container_l }} L |
| Rainfall allowance | {{ rainfall_allowance_l }} L |
| Provided bund volume | {{ provided_bund_volume_l }} L |
| Fire growth alpha | {{ fire_growth_alpha_kw_s2 }} kW/s2 |
| Design fire time | {{ design_fire_time_s }} s |
| Provided visibility | {{ provided_visibility_m }} m |
| Required visibility | {{ required_visibility_m }} m |
| Horn count | {{ horn_count }} |
| Horn current | {{ horn_current_a }} A |
| Strobe count | {{ strobe_count }} |
| Strobe current | {{ strobe_current_a }} A |
| Panel current | {{ panel_current_a }} A |
| NAC supply capacity | {{ nac_supply_capacity_a }} A |
| Alarm load | {{ alarm_load_w }} W |
| Alarm runtime | {{ alarm_runtime_h }} h |
| Alarm battery capacity | {{ alarm_battery_capacity_kwh }} kWh |
| Isolated drains | {{ isolated_drain_count }} |
| Total drains | {{ total_drain_count }} |
| Allowed spill response time | {{ allowed_spill_response_min }} min |
| Planned spill response time | {{ planned_spill_response_min }} min |

## Required Checks

- Required bund volume equals largest container plus rainfall allowance for this source pack.
- Fire HRR equals alpha times design fire time squared.
- NAC current is the sum of horns, strobes, and panel current.
- Alarm battery energy covers the alarm load over the required runtime.
- Drain isolation fraction confirms every listed drain is isolated.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack, preserve the source object IDs above, and state whether the baseline checks pass.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable source-pack hardening, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "required_bund_volume_l": <numeric_value>,
  "bund_volume_margin_l": <numeric_value>,
  "fire_hrr_kw": <numeric_value>,
  "visibility_margin_m": <numeric_value>,
  "nac_current_a": <numeric_value>,
  "nac_headroom_a": <numeric_value>,
  "alarm_battery_required_kwh": <numeric_value>,
  "alarm_battery_margin_kwh": <numeric_value>,
  "drain_isolation_fraction": <numeric_value>,
  "spill_response_margin_min": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
