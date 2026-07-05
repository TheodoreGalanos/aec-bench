# ABOUTME: Defines the future executable verifier contract for the facade source pack.
# ABOUTME: Keeps implementation acceptance criteria concrete without adding runtime code.

# Facade Source Pack Verifier Implementation Brief

This is a docs-only implementation brief for future benchmark hardening. It is not executable verifier code, not a generated benchmark instance, and not an issued facade engineering calculation.

The future verifier should treat `facade_redrawn_calculation_source_pack` as a closed task-owned source pack. It should grade against embedded files and excerpts only, not live vendor lookups, hidden standards text, or external manufacturer calculators.

## Inputs

The verifier should read:

- `project.json` for pack identity, unit system, geometry scale, drawing references, source-family roles, and source-policy boundary.
- `elevation-redrawn.svg` and any selected variant elevation for visible labels, drawing bounds, opening geometry, pressure-zone markup, and support coordinates.
- `geometry-oracle.csv` for drawing bounds, pressure-zone extents, opening extents, support-point coordinates, and verifier roles.
- `pressure-schedule.csv` for zone pressure, load combination, tributary rule, and governing pressure flag.
- `support-schedule.csv` for support family, selected bracket/profile rows, fixed/sliding role, tributary dimensions, fastener count, and anchor row.
- `capacity-excerpts.yaml` for embedded bracket, anchor, and source-family excerpt values.
- `anchor-check-oracle.csv` for selected anchor geometry, demand, resistance, utilization, pass flags, and governing anchor check.
- `calculation-oracle.csv` for expected tributary area, wind load, dead load, bracket utilization, anchor utilization, governing utilization, governing component, and pass/fail status.
- `verification-cases.yaml` for baseline and negative-case expectations.
- `variant-matrix.yaml`, `variant-source-overlays.yaml`, and `variants/variant-source-files.yaml` for docs-only variant selection, expanded source files, expected result, and failure-stage mapping.
- `expected-output.md` for required memo, annotated-elevation, table, and source-policy response content.

## Stage Contract

The verifier should produce one structured result per stage:

1. `manifest`: all required source-pack files exist, parse, and match the pack identity.
2. `drawing_geometry`: SVG labels and viewBox are present; support labels are visible in the selected elevation.
3. `geometry_bounds`: drawing bounds match `project.json` scale and the `DRAWING` row in `geometry-oracle.csv`.
4. `opening_geometry`: opening rows match visible opening rectangles and scale-derived dimensions.
5. `support_coordinates`: support points exist, use matching labels, and fall within the expected pressure-zone extent.
6. `pressure_zone`: every support row joins to a pressure-schedule row and inherits the expected pressure/load-combination basis.
7. `load_derivation`: tributary area, wind load, and dead load recompute from source rows within `verification-rules.yaml` tolerance.
8. `support_lookup`: bracket/profile rows named by the support schedule are present in the embedded capacity excerpts.
9. `anchor_lookup`: selected anchor rows join from support schedule to capacity excerpts and anchor-check oracle.
10. `anchor_geometry`: embedment, edge-distance, and spacing flags match the embedded minimums.
11. `anchor_demand`: anchor tension/shear demand traces to the calculation-oracle wind/dead-load rows.
12. `utilization`: bracket, anchor, combined, governing, and pass/fail values recompute within tolerance.
13. `memo_traceability`: solver output identifies governing support, governing component, source files, and embedded excerpt families.
14. `source_policy`: solver output does not claim live vendor retrieval, issued-project status, or hidden standard criteria as the grading basis.

## Variant Handling

The verifier should accept one selected variant at a time:

- If no variant is selected, use the baseline source files.
- If a variant has expanded source files in `variants/variant-source-files.yaml`, use those files in preference to the baseline files for the listed paths and reuse the listed baseline files for the rest.
- If future implementation uses `variant-source-overlays.yaml` directly, it should apply exactly one overlay to a clean baseline pack before verification.
- The selected variant's `expected_result` and `failure_stage` must match both `variant-matrix.yaml` and `variants/variant-source-files.yaml`.
- Passing variants must complete all required checks and report the governing row.
- Failing variants must fail at the localized stage named in the matrix/index and should not cascade into unrelated diagnostics before the intended failure is reported.

## Diagnostics

Each failed check should report:

- `stage`: one of the failure-localization values in `verification-rules.yaml`.
- `source_file`: the source-pack file that failed or created the mismatch.
- `row_id`: the support, anchor, geometry, pressure-zone, or variant identifier where applicable.
- `expected`: the recomputed or source-pack value.
- `actual`: the solver-supplied or parsed value.
- `message`: a concise explanation suitable for benchmark feedback.

Diagnostics should preserve root cause. For example, an anchor edge-distance failure should not be reported as a generic utilization failure unless the geometry checks pass and the utilization calculation itself is wrong.

## Acceptance Evidence

Before the facade pack is treated as benchmark-ready, future implementation should leave evidence for:

- Baseline pass result using the unmodified seed pack.
- Negative-case failures for manifest, drawing label, geometry bounds, opening geometry, support coordinates, pressure zone, load derivation, anchor lookup, anchor geometry, anchor demand, utilization, source policy, and memo traceability.
- Positive variant pass results for `added_opening_edge_support` and `reentrant_corner_pressure_governing`.
- Negative variant localized failures for `anchor_edge_distance_failure`, `anchor_spacing_failure`, and `corner_pressure_over_limit`.
- A fixture-generation or runtime packaging manifest showing how the source pack is imported into the benchmark path.

Until that evidence exists, this pack remains research material rather than a completed benchmark fixture.
