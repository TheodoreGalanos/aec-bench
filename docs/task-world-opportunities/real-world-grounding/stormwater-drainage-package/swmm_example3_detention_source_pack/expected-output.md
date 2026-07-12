# ABOUTME: Expected answer and evidence boundaries for the SWMM Example 3 fixture route.
# ABOUTME: Defines source-traceable stormwater outputs without adding executable runtime code.

# Expected Output For SWMM Example 3 Detention Fixture

## Answer Shape

A benchmark answer should read like a short design-check memo, not a naked calculation. It should cite the EPA source pack, summarize the model basis, identify the detention/outlet design intent, report expected target values, and disclose known source-boundary issues.

Required sections:

- Source provenance and file inventory.
- Model basis and rainfall/design storms.
- Detention pond and outlet structure summary.
- Peak-release and WQCV target table.
- Report-output status: generated report evidence if available, or an explicit unavailable-engine diagnostic if not.
- Verification notes and unresolved project-grade evidence gaps.

## Required Source Claims

The answer should state that:

- The fixture is based on EPA SWMM Applications Manual Example 3, "Detention Pond Design."
- `Example3.inp` is the selected model file, paired with `Example3.ini` and `Site-Post.jpg`.
- The model uses CFS flow units, Horton infiltration, Dynamic Wave routing, one rain gage, seven subcatchments, one storage unit, three orifices, one weir, and a post-development site backdrop.
- The selected task is public teaching/example evidence, not a public municipal approval package.
- Current research evidence is static source-pack evidence; generated SWMM report continuity, node/link summary, and binary-output checks remain future runtime work unless an implementation supplies a verified SWMM engine and report artifacts.

## Required Target Values

The answer should preserve these source-traceable values:

| Item | Expected value |
| --- | --- |
| WQCV depth | 0.23 in |
| WQCV volume | 24,162 ft3 |
| WQCV drawdown target | 40 h |
| Final Or1 drainage time | 40:12 hr:min |
| Storage unit | `SU1`, invert 4956 ft, max depth 6 ft |
| Storage curve | `(0, 14706)`, `(2.22, 19659)`, `(2.3, 39317)`, `(6, 52644)` as depth-ft/area-ft2 pairs |
| 2-year target peak | 4.14 cfs pre-development |
| 2-year final controlled peak | 4.11 cfs |
| 2-year final max depth | 2.21 ft |
| 10-year target peak | 7.34 cfs pre-development |
| 10-year final controlled peak | 7.32 cfs |
| 10-year final max depth | 3.17 ft |
| 100-year target peak | 31.6 cfs pre-development |
| 100-year final controlled peak | 31.2 cfs |
| 100-year final max depth | 5.42 ft |
| Final freeboard | 0.53 ft, with the manual freeboard arithmetic using 5.43 ft |

## Required Outlet Description

The answer should identify the staged outlet logic:

- `Or1`: side rectangular orifice from `SU1` to `J_out`, offset 0 ft, coefficient 0.65, dimensions 0.3 ft by 0.25 ft, WQCV drawdown role.
- `Or2`: side rectangular orifice from `SU1` to `J_out`, offset 1.5 ft, coefficient 0.65, dimensions 0.5 ft by 2 ft, 2-year peak control role.
- `Or3`: side rectangular orifice from `SU1` to `J_out`, offset 2.22 ft, coefficient 0.65, dimensions 0.25 ft by 0.35 ft, 10-year peak control role.
- `W1`: transverse rectangular weir from `SU1` to `J_out`, offset 3.17 ft, coefficient 3.3, opening 2.83 ft by 1.75 ft, 100-year overflow role.

## Required Boundary Notes

The answer should explicitly disclose:

- The manual/model time-step mismatch: manual narrative describes 15-second report, wet, and routing steps; `Example3.inp` has 1-minute report and wet steps plus 15-second routing.
- The manual/model area-rounding mismatch: manual WQCV arithmetic uses 28.94 acres; `Example3.inp` rounded subcatchment rows sum to 28.92 acres.
- The source-pack is sufficient for a public executable teaching fixture, but not enough to claim municipal acceptance, local council compliance, or project-stage plan/profile review.
- The source-pack does not currently prove generated continuity summaries, node/link summary rows, or binary-output time series because the temporary `swmm-toolkit` native binding route failed in this environment.

## Rejection Triggers

The answer should fail if it:

- Omits EPA source provenance or claims the files are private/project-approved artifacts.
- Invents local drainage criteria, rainfall sources, or council acceptance.
- Uses unsupported outlet dimensions or storm targets.
- Ignores the staged orifice/weir outlet structure.
- Treats manual narrative and `Example3.inp` differences as exact agreement.
- Reports final discharges without connecting them to the source files and manual target table.
- Claims report-output, continuity, node/link, or binary time-series evidence was generated in this checkout without a verified SWMM engine artifact.
