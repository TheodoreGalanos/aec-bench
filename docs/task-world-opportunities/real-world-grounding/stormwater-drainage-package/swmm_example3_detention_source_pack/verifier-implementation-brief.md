# ABOUTME: Docs-only verifier implementation brief for the SWMM Example 3 detention source pack.
# ABOUTME: Maps source files, report outputs, diagnostics, and blocked runtime evidence to future verifier work.

# SWMM Example 3 Verifier Implementation Brief

## Scope

This brief translates the docs-only `swmm_example3_detention_source_pack` into future executable verifier stages. It is not runtime code and does not claim that a SWMM report was generated in this checkout.

The current packet is strong enough to verify source identity, model structure, manual design targets, and answer traceability from static files. It is not yet strong enough to verify dynamic SWMM report outputs, continuity summaries, node/link summary tables, or binary-output time series. A temporary attempt to run `Example3.inp` through `swmm-toolkit` failed at native binding import, so report-output evidence remains an implementation gap rather than a hidden assumption.

## Inputs

Future runtime packaging should acquire or materialize:

- `Example3.inp`
- `Example3.ini`
- `Site-Post.jpg`
- `Swmm_Apps_Manual.pdf`
- A generated `Example3.rpt`
- A generated `Example3.out`, if binary-output checks are in scope
- This packet's `source-manifest.yaml`, `model-summary.yaml`, `expected-output.md`, `verification-rules.yaml`, and `verification-cases.yaml`

The verifier must not assume EPA source files were vendored in this research pass. It should either download from the official EPA URL and verify hashes or consume an approved source bundle with the same hashes.

## Stage 1: Source Acquisition

Checks:

- Confirm the EPA Applications Manual zip SHA-256.
- Confirm nested `files.zip` SHA-256.
- Confirm `Swmm_Apps_Manual.pdf`, `Example3.inp`, `Example3.ini`, and `Site-Post.jpg` SHA-256.
- Confirm `Example3.inp` references `Site-Post.jpg` in `[BACKDROP]`.
- Confirm the answer does not claim municipal approval, project issue status, or task-owned source-file redistribution.

Diagnostics:

- `missing_source_file`
- `source_hash_mismatch`
- `backdrop_reference_missing`
- `unsupported_project_approval_claim`

## Stage 2: Static Model Parse

Checks:

- Parse `[OPTIONS]` and confirm CFS, Horton infiltration, Dynamic Wave routing, 1-minute report/wet steps, 1-hour dry step, 15-second routing step, no ponding, and depth offsets.
- Parse object sections and confirm counts for subcatchments, junctions, outfalls, storage units, conduits, orifices, weirs, xsections, rainfall time-series rows, coordinates, vertices, polygons, and backdrop files.
- Confirm seven subcatchments route through the post-development drainage system to `SU1` and then through the outlet structure to `J_out`/`O2`.
- Confirm `SU1` uses the expected tabular storage curve.
- Confirm `Or1`, `Or2`, `Or3`, and `W1` have the expected inlets, outlets, offsets, discharge coefficients, shapes, dimensions, and staged design roles.

Diagnostics:

- `mismatched_options`
- `missing_model_section`
- `mismatched_object_counts`
- `mismatched_storage_curve`
- `mismatched_outlet_rows`
- `broken_outlet_path`

## Stage 3: Manual Target Trace

Checks:

- Confirm answer includes the WQCV depth, WQCV volume, drawdown target, and final `Or1` drainage time.
- Confirm answer includes 2-year, 10-year, and 100-year pre-development peak targets, uncontrolled post-development peaks, final controlled peaks, and final maximum storage depths.
- Confirm answer identifies the manual/model time-step mismatch when discussing run settings.
- Confirm answer identifies or tolerates the 28.94-acre manual WQCV basis versus 28.92-acre rounded `.inp` area sum.
- Confirm answer treats manual targets as source-bounded values, not as newly generated outputs from this checkout.

Diagnostics:

- `missing_target_value`
- `target_value_out_of_tolerance`
- `undisclosed_source_boundary_issue`
- `generated_output_claim_without_report`

## Stage 4: Report Output Checks

This stage is intentionally future work until a reliable SWMM engine is available.

When implemented, it should run the verified `Example3.inp` and inspect `Example3.rpt` for:

- Runoff continuity summary.
- Flow-routing continuity summary.
- Node flooding/surcharge status.
- Node depth/inflow summary rows for `SU1`, `J_out`, and critical upstream junctions.
- Link flow/depth summary rows for `Or1`, `Or2`, `Or3`, `W1`, `C11`, and `C_out`.
- Storage-unit max depth and outlet peak flow values close to the manual target values, allowing documented differences from manual narrative time-step settings.
- Any engine warnings, nonconvergence notes, or continuity errors large enough to invalidate fixture use.

For binary-output checks, the verifier may additionally inspect time-series data for:

- `SU1` depth over time.
- `Or1`, `Or2`, `Or3`, and `W1` flow over time.
- Outfall flow at `O2`.
- Peak timing consistency across storage and outlet elements.

Diagnostics:

- `swmm_engine_unavailable`
- `report_file_missing`
- `binary_output_missing`
- `continuity_error_exceeds_threshold`
- `node_summary_missing`
- `link_summary_missing`
- `dynamic_result_out_of_tolerance`

## Stage 5: Answer Evaluation

Checks:

- Require a design-check memo shape rather than a naked numeric answer.
- Reward traceable source use: EPA source provenance, selected file names, model settings, source-boundary disclosure, target table, outlet logic, and unresolved project-grade evidence gaps.
- Penalize invented local criteria, invented report generation, unsupported municipal acceptance, missing mismatch disclosure, or final-number claims disconnected from the source pack.

Minimum acceptance evidence:

- Source acquisition log.
- Static parse summary.
- Manual target trace summary.
- Report-output summary or explicit `swmm_engine_unavailable` diagnostic.
- Answer-evaluation diagnostic table.

## Current Runtime Boundary

This research pass attempted a temporary `swmm-toolkit` route. The pure Python package import and metadata inspection worked, but importing `swmm.toolkit.solver` or `swmm.toolkit.output` exited with code 1 and no Python traceback. No `swmm5` or `runswmm` executable was available locally.

Therefore, this packet should be treated as a static source-pack and verifier-contract hardening pass. Runtime output evidence remains unresolved until a controlled SWMM engine path is available.
