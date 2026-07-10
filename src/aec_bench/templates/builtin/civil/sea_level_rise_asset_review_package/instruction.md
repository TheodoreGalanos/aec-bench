You are a civil/coastal engineer checking a task-owned synthetic SSC-04 sea-level-rise scenario and asset-level review package.

Use only the task-owned synthetic source pack values shown below for numeric grading. External climate-scenario, storm-tide, service-threshold, adaptation-option, and asset-review workflows shape the practice context only; they are not extra data sources for this instance.

## Scene

- Product family: `SSC-04-LH-06`
- Asset register: `ASSET-04-REGISTER-06`
- Sea-level-rise scenario table: `SLR-04-SCENARIO-06`
- Storm tide table: `STORM-04-TIDE-06`
- Service criterion: `SERVICE-04-CRITERION-06`
- Adaptation option sheet: `ADAPT-04-OPTION-06`
- Asset review memo: `MEMO-04-REVIEW-06`

## Source Values

| Item | Value |
|------|-------|
| Present high tide level | {{ present_high_tide_level_m }} m |
| Sea-level-rise allowance | {{ sea_level_rise_allowance_m }} m |
| Storm surge allowance | {{ storm_surge_allowance_m }} m |
| Wave allowance | {{ wave_allowance_m }} m |
| Asset elevation | {{ asset_elevation_m }} m |
| Required freeboard | {{ required_freeboard_m }} m |
| Service threshold | {{ service_threshold_m }} m |
| Adaptation budget | {{ adaptation_budget_usd }} USD |
| Selected adaptation cost | {{ selected_adaptation_cost_usd }} USD |
| Avoided damage | {{ avoided_damage_usd }} USD |
| Traced scenarios | {{ traced_scenarios }} |
| Required scenarios | {{ required_scenarios }} |

## Checks

- Future stillwater level equals present high tide plus sea-level-rise allowance plus storm surge allowance.
- Future design level equals future stillwater level plus wave allowance.
- Asset freeboard margin equals asset elevation minus future design level and required freeboard.
- Service threshold exceedance equals future stillwater level minus service threshold, clipped at zero.
- Adaptation raise required equals future design level plus required freeboard minus asset elevation, clipped at zero.
- Adaptation cost margin equals adaptation budget minus selected adaptation cost.
- Benefit-cost ratio equals avoided damage divided by selected adaptation cost.
- Scenario trace score equals traced scenarios divided by required scenarios.
- Overall pass score is `1.0` only when freeboard, cost, benefit-cost, and scenario trace checks pass; otherwise it is `0.0`.

## Output Format

Write a compact asset review memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the object IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "future_stillwater_level_m": <numeric_value>,
  "future_design_level_m": <numeric_value>,
  "asset_freeboard_margin_m": <numeric_value>,
  "service_threshold_exceedance_m": <numeric_value>,
  "adaptation_raise_required_m": <numeric_value>,
  "adaptation_cost_margin_usd": <numeric_value>,
  "benefit_cost_ratio": <numeric_value>,
  "scenario_trace_score": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
