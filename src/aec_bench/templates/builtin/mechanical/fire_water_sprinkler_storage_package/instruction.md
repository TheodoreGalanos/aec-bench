You are a fire protection engineer checking a task-owned synthetic SSC-19 fire-water, sprinkler demand, riser pressure, pump boost, and storage package.

Use only the task-owned synthetic source pack values shown below for numeric grading. NFPA 13, NFPA 291, EPA EPANET, FM property loss prevention data sheets, and AHJ fire-protection workflows shape the context only; this instance does not run hydraulic network software, parse real hydrant-test forms, verify a code clause, prove AHJ approval, or prove full fire-protection compliance.

## Scene

- Fire-water design case: `CASE-SSC19-FIRE-001`
- Hazard and storage basis: `HAZ-19-STORAGE-01`
- Hydrant test form: `HYD-19-TEST-01`
- Water-supply curve: `CURVE-19-SUPPLY-01`
- Sprinkler layout and remote area: `SPR-19-AREA-01`
- Sprinkler head schedule: `SPR-19-HEAD-01`
- Riser schematic: `PIPE-19-RISER-01`
- Elevation zone record: `ELEV-19-ZONE-01`
- Fire-water pump boost schedule: `PUMP-19-BOOST-01`
- Fire-water storage tank: `TANK-19-STORAGE-01`
- AHJ design criterion: `CRIT-19-AHJ-01`
- Fire-water memo: `MEMO-19-FIRE-WATER-01`

## Sprinkler Demand Basis

| Item | Value |
|------|-------|
| Remote sprinkler design area | {{ sprinkler_design_area_ft2 }} ft2 |
| Sprinkler density | {{ sprinkler_density_gpm_ft2 }} gpm/ft2 |
| Hose allowance | {{ hose_allowance_gpm }} gpm |
| Sprinkler K factor | {{ sprinkler_head_k_factor_gpm_sqrt_psi }} gpm/sqrt(psi) |
| Minimum remote-head pressure | {{ minimum_head_pressure_psi }} psi |
| Installed remote-area head count | {{ installed_remote_head_count }} |

Sprinkler checks:

- Sprinkler demand equals design area times sprinkler density.
- Total fire demand equals sprinkler demand plus hose allowance.
- Sprinkler head discharge equals `sprinkler_head_k_factor_gpm_sqrt_psi x sqrt(minimum_head_pressure_psi)`.
- Required remote-head count equals `ceil(sprinkler_demand_gpm / sprinkler_head_discharge_gpm)`.
- Remote-head count margin equals installed remote head count minus required remote-head count.

## Water Supply And Riser Basis

| Item | Value |
|------|-------|
| Hydrant static pressure | {{ hydrant_static_pressure_psi }} psi |
| Hydrant residual pressure | {{ hydrant_residual_pressure_psi }} psi |
| Hydrant test flow | {{ hydrant_test_flow_gpm }} gpm |
| Target residual pressure | {{ target_residual_pressure_psi }} psi |
| Riser pipe length | {{ riser_pipe_length_ft }} ft |
| Riser fitting equivalent length | {{ riser_fitting_equivalent_length_ft }} ft |
| Riser pipe internal diameter | {{ riser_pipe_internal_diameter_in }} in |
| Hazen-Williams C | {{ hazen_williams_c }} |
| Elevation gain | {{ elevation_gain_ft }} ft |

Water-supply and riser checks:

- Pressure drop at test flow equals static pressure minus residual pressure.
- Supply curve coefficient equals `hydrant_test_flow_gpm / pressure_drop_test_psi^0.54`.
- Available flow at the target residual pressure equals `supply_curve_coefficient x (hydrant_static_pressure_psi - target_residual_pressure_psi)^0.54`.
- Water-supply flow margin equals available flow at target residual pressure minus total fire demand.
- Residual pressure at total fire demand equals `hydrant_static_pressure_psi - (total_fire_demand_gpm / supply_curve_coefficient)^(1 / 0.54)`.
- Friction loss per foot equals `4.52 x total_fire_demand_gpm^1.85 / (hazen_williams_c^1.85 x riser_pipe_internal_diameter_in^4.87)`.
- Equivalent length equals riser pipe length plus fitting equivalent length.
- Total friction loss equals friction loss per foot times equivalent length.
- Elevation pressure loss equals `0.433 x elevation_gain_ft`.
- Available riser pressure equals residual pressure at demand minus total friction loss and elevation pressure loss.

## Pump Boost And Storage Basis

| Item | Value |
|------|-------|
| Selected fire-water pump boost | {{ pump_boost_pressure_psi }} psi |
| Remote-area pressure allowance | {{ remote_area_allowance_psi }} psi |
| Required storage duration | {{ required_duration_min }} min |
| Available fire-water storage | {{ available_storage_gal }} gal |

Pump and storage checks:

- Boosted riser pressure equals available riser pressure plus selected fire-water pump boost.
- Required riser pressure equals minimum remote-head pressure plus remote-area pressure allowance.
- Pressure margin equals boosted riser pressure minus required riser pressure.
- Required storage equals total fire demand times required storage duration.
- Storage margin equals available storage minus required storage.
- Overall pass score is `1.0` only when remote-head count margin, water-supply flow margin, pressure margin, and storage margin are all non-negative; otherwise it is `0.0`.

## Output Format

Write a compact memo to `/workspace/output.md`. Include a source-boundary statement that this is a task-owned synthetic source pack. Explain the calculations briefly, preserve the object IDs above, and state whether the baseline source pack passes the current docs-only checks.

Do not claim authority approval, accepted project evidence, hydraulic software export validity, full standards compliance, executable real source-pack parsing, generated EPANET/fire-model evidence, generated benchmark readiness, or benchmark readiness.

Include a fenced JSON block with exactly these numeric keys:

```json
{
  "sprinkler_demand_gpm": <numeric_value>,
  "total_fire_demand_gpm": <numeric_value>,
  "sprinkler_head_discharge_gpm": <numeric_value>,
  "required_remote_head_count": <numeric_value>,
  "remote_head_count_margin": <numeric_value>,
  "pressure_drop_test_psi": <numeric_value>,
  "supply_curve_coefficient": <numeric_value>,
  "available_flow_20psi_gpm": <numeric_value>,
  "water_supply_flow_margin_gpm": <numeric_value>,
  "residual_pressure_at_demand_psi": <numeric_value>,
  "friction_loss_per_ft_psi": <numeric_value>,
  "equivalent_length_ft": <numeric_value>,
  "total_friction_loss_psi": <numeric_value>,
  "elevation_pressure_loss_psi": <numeric_value>,
  "available_riser_pressure_psi": <numeric_value>,
  "boosted_riser_pressure_psi": <numeric_value>,
  "required_riser_pressure_psi": <numeric_value>,
  "pressure_margin_psi": <numeric_value>,
  "required_storage_gal": <numeric_value>,
  "storage_margin_gal": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```
