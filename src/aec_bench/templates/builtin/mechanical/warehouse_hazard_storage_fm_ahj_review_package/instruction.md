You are a fire protection engineer checking a task-owned synthetic SSC-19 warehouse hazard, storage arrangement, and FM/AHJ review package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Warehouse hazard classification, sprinkler demand, FM-style property review, and AHJ comment workflows shape the context only; this instance does not validate a real standard, accepted review, hydraulic model, or authority approval.

## Scene

- Product: `SSC-19-LH-05`
- Storage layout: `STORE-19-LAYOUT-05`
- Commodity hazard table: `HAZ-19-COMMODITY-05`
- Sprinkler basis: `SPR-19-BASIS-05`
- FM/AHJ review register: `REVIEW-19-FM-AHJ-05`
- Calculation appendix: `CALC-19-APPENDIX-05`
- Hazard memo: `MEMO-19-HAZARD-05`

## Source Values

| Item | Value |
| --- | --- |
| Storage area | {{ storage_area_ft2 }} ft2 |
| Storage height | {{ storage_height_ft }} ft |
| Aisle width | {{ aisle_width_ft }} ft |
| Required aisle width | {{ required_aisle_width_ft }} ft |
| Commodity hazard factor | {{ commodity_hazard_factor }} |
| Base sprinkler density | {{ base_density_gpm_ft2 }} gpm/ft2 |
| Remote area | {{ remote_area_ft2 }} ft2 |
| Hose allowance | {{ hose_allowance_gpm }} gpm |
| Sprinkler K factor | {{ sprinkler_k_factor }} |
| Minimum head pressure | {{ minimum_head_pressure_psi }} psi |
| Available supply | {{ available_supply_gpm }} gpm |
| Available pressure | {{ available_pressure_psi }} psi |
| Required pressure | {{ required_pressure_psi }} psi |
| Review comments | {{ review_comments }} |
| Resolved comments | {{ resolved_comments }} |
| Response sections | {{ response_sections }} |
| Required response sections | {{ required_response_sections }} |
| Critical open comments | {{ critical_open_comments }} |

## Checks

- Sprinkler density equals commodity hazard factor times base sprinkler density.
- Sprinkler demand equals remote area times sprinkler density.
- Total fire demand equals sprinkler demand plus hose allowance.
- Required remote-head count equals `ceil(sprinkler_demand_gpm / (sprinkler_k_factor x sqrt(minimum_head_pressure_psi)))`.
- Water supply margin equals available supply minus total fire demand.
- Pressure margin equals available pressure minus required pressure.
- Comment resolution fraction equals resolved comments divided by review comments.
- Authority response score equals response sections divided by required response sections.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Preserve the source IDs above and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, hydraulic software export validity, full standards compliance, executable real source-pack parsing, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "storage_area_ft2": <numeric_value>,
  "storage_height_ft": <numeric_value>,
  "sprinkler_density_gpm_ft2": <numeric_value>,
  "sprinkler_demand_gpm": <numeric_value>,
  "total_fire_demand_gpm": <numeric_value>,
  "required_remote_head_count": <numeric_value>,
  "water_supply_margin_gpm": <numeric_value>,
  "pressure_margin_psi": <numeric_value>,
  "aisle_width_margin_ft": <numeric_value>,
  "comment_resolution_fraction": <numeric_value>,
  "authority_response_score": <numeric_value>,
  "critical_open_comments": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
