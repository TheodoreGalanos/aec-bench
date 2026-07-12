# ABOUTME: Docs-only hardening plan for the stormwater SWMM Example 3 fixture route.
# ABOUTME: Maps the public EPA source bundle to future benchmark packaging and verifier work.

# SWMM Example 3 Detention Source-Pack Plan

## Scope

This packet hardens `stormwater-drainage-package` around one public, executable source family: EPA SWMM Applications Manual Example 3, "Detention Pond Design."

The packet is deliberately docs-only. It does not vendor EPA files, implement runtime code, or claim that a municipal authority accepted the example as a project design package. It makes the future fixture boundary concrete enough that implementation work can download the official EPA bundle, verify hashes, select `Example3.inp`, and check a model-reading or design-memo answer against explicit source and expected-output requirements.

## Why Example 3

Example 3 is the best near-term hardening target because it exercises the same long-horizon stormwater chain the composite task wants to test:

- A developed catchment represented as seven SWMM subcatchments and a mapped site backdrop.
- Rainfall/runoff inputs for 2-year, 10-year, and 100-year design storms.
- Surface conveyance from the prior post-development model.
- A storage unit `SU1` with a tabular storage curve.
- Three side orifices and one transverse weir used as a staged outlet structure.
- Explicit manual design targets for pre-development peak-release matching, WQCV drawdown, maximum pond depth, and freeboard.
- A future verifier path that can check model sections, object joins, target values, and memo traceability without private project data.

## Source Priority

Future packaging should treat the sources in this order:

1. The official EPA SWMM page proves the source is EPA-published and current enough to locate the Applications Manual bundle.
2. The downloaded outer zip and nested `files.zip` hashes prove the exact source bundle inspected for this pass.
3. `Example3.inp` is authoritative for model-file structure, object names, counts, and SWMM option settings.
4. `Swmm_Apps_Manual.pdf` is authoritative for narrative design intent and expected design target values.
5. Where the manual narrative and `Example3.inp` differ, the verifier must report the mismatch instead of silently choosing one.

Two known source-boundary issues are part of the hardening evidence:

- The manual says the final comparison models used 15-second report, wet-weather, and routing time steps, while `Example3.inp` uses 1-minute report and wet steps with a 15-second routing step.
- The manual calculates WQCV from a 28.94-acre total, while the rounded `Example3.inp` subcatchment areas sum to 28.92 acres.

These are tolerancing and provenance issues, not reasons to discard the source.

## Future Fixture Contents

The future runtime source pack should contain or reconstruct:

- `Example3.inp`, verified against the EPA source-bundle hash and per-file hash in `source-manifest.yaml`.
- `Example3.ini`, verified against the per-file hash in `source-manifest.yaml`.
- `Site-Post.jpg`, verified against the per-file hash in `source-manifest.yaml`.
- A short provenance note pointing to the EPA SWMM page and Applications Manual zip URL.
- A selected target ledger derived from `model-summary.yaml` and `expected-output.md`.
- A verifier implementation brief mapping source acquisition, static parsing, manual target trace, report-output checks, and answer evaluation.
- A generated SWMM run report or parsed report excerpt, if runtime packaging later includes an approved SWMM engine.
- A verifier diagnostic report covering source presence, model sections, design targets, and known manual/model boundary mismatches.

## Future Task Shape

A benchmark instance can ask the agent to review the source pack and prepare a design-check memo. The answer should identify:

- The rainfall/design-storm basis and selected time series.
- The pre-development peak-release targets for 2-year, 10-year, and 100-year storms.
- The WQCV volume and drawdown target.
- The storage unit, storage curve, and outlet structure used to satisfy those targets.
- The expected final controlled peak discharges and maximum storage depths.
- Any source inconsistencies or missing project-grade evidence.

The verifier should reward traceable source use and penalize invented local criteria, invented municipal approval status, missing mismatch disclosure, or final-number checks that ignore the EPA source boundary.

## Runtime Evidence Boundary

A temporary `swmm-toolkit` execution route was investigated after this packet was created. The pure Python package import and metadata inspection worked, but importing the native `solver` or `output` bindings exited without a Python traceback, and no local `swmm5` or `runswmm` executable was available. The packet therefore does not contain generated report-output evidence. Future implementation must use a controlled SWMM engine path before claiming continuity summaries, node/link summaries, binary-output time series, or dynamic result validation.
