You are a civil/coastal engineer checking a task-owned synthetic SSC-04 wave runup, freeboard, and asset protection package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External linear-wave, shoaling, breaking, runup, freeboard, and armor-sizing workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-04-LH-02`
- Wave climate table: `WAVE-04-CLIMATE-02`
- Shore profile: `PROFILE-04-SHORE-02`
- Asset level table: `ASSET-04-LEVEL-02`
- Armor/barrier schedule: `ARMOR-04-SCHED-02`
- Design horizon criterion: `CRIT-04-HORIZON-02`
- Asset protection memo: `MEMO-04-PROTECT-02`

## Source Values

| Item | Value |
|------|-------|
| Offshore wave height | {{ offshore_wave_height_m }} m |
| Wave period | {{ wave_period_s }} s |
| Shoaling coefficient | {{ shoaling_coefficient }} |
| Nearshore depth | {{ nearshore_depth_m }} m |
| Breaker index | {{ breaker_index }} |
| Runup coefficient | {{ runup_coefficient }} |
| Slope factor | {{ slope_factor }} |
| Stillwater level | {{ stillwater_level_m }} m |
| Asset platform level | {{ asset_platform_level_m }} m |
| Required freeboard | {{ required_freeboard_m }} m |
| Selected armor mass | {{ selected_armor_mass_t }} t |
| Required armor mass | {{ required_armor_mass_t }} t |

## Checks

- Deepwater wavelength equals `9.81 x wave_period_s^2 / (2 x pi)`.
- Nearshore wave height equals offshore wave height times the source-owned shoaling coefficient.
- Breaking height limit equals breaker index times nearshore depth.
- Runup equals runup coefficient times nearshore wave height times slope factor.
- Total water level equals stillwater level plus runup.
- Freeboard margin equals asset platform level minus total water level and required freeboard.
- Armor stability margin equals selected armor mass minus required armor mass.
- Overall pass score is `1.0` only when the wave height stays below the breaking limit and the freeboard and armor margins are non-negative; otherwise it is `0.0`.

## Output Format

Write a compact asset protection memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "deepwater_wavelength_m": <numeric_value>,
  "shoaling_coefficient": <numeric_value>,
  "nearshore_wave_height_m": <numeric_value>,
  "breaking_height_limit_m": <numeric_value>,
  "breaking_margin_m": <numeric_value>,
  "runup_2_percent_m": <numeric_value>,
  "total_water_level_m": <numeric_value>,
  "freeboard_margin_m": <numeric_value>,
  "armor_stability_margin_t": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
