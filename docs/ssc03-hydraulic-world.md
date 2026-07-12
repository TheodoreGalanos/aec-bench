# ABOUTME: Explains the PR18 public hydraulic mini-world, evidence chain, and command-line workflow.
# ABOUTME: Separates deterministic screening calculations from SWMM, model actions, and project approval.

# SSC-03 Deterministic Hydraulic World

## What PR18 adds

PR18 adds one small executable engineering world:

```text
two synthetic catchments
  -> triangular runoff hydrograph
  -> detention basin with changing storage area
  -> controlled circular orifice
  -> emergency rectangular weir
  -> two pipes and two pits
  -> fixed downstream tailwater
  -> discharge, velocity, HGL, storage, freeboard, and continuity checks
```

The world ID is `ssc03.public.detention-network.v1`. It runs locally without a model provider, credentials, external solver, or network download.

This is a benchmark-owned hydraulic **screening kernel**. It is not EPA SWMM, does not claim SWMM-equivalent fidelity, and is not evidence of authority approval, standards compliance, or a completed project design.

## Why PR18 does not use SWMM

PR18 reran the engine compatibility gate before choosing an implementation. The official `swmm-toolkit==0.17.0` package publishes a macOS ARM64 wheel and its ordinary Python namespace imports successfully. However, importing either `swmm.toolkit.solver` or `swmm.toolkit.output` kills the process with exit status 137 on both Python 3.13.2 and 3.12.9. No `swmm5` or `runswmm` executable is installed.

The exact commands, platform, wheel identity, outputs, and exit statuses are preserved in [the compatibility matrix](ssc03-swmm-compatibility-matrix.yaml). Because the required local native route fails before a model can run, PR18 follows the roadmap's explicit fallback rather than adding a broken dependency.

## How the EPA Example 3 packet is used

The seven-file EPA SWMM Example 3 research packet from commit `1a46f13` is restored at its original path:

`docs/task-world-opportunities/real-world-grounding/stormwater-drainage-package/swmm_example3_detention_source_pack/`

Its exact bytes are protected by a regression test. The packet remains a provenance, manual-target, and future-verifier reference. It describes an imperial SWMM model with seven subcatchments. It is not silently transformed into this metric two-catchment world, and the actual EPA model files are not vendored or downloaded at runtime.

## Public source state

The synthetic source state contains six separately revisioned and hashed sections:

| Section | Contents |
| --- | --- |
| Catchments | `CATCH-A` and `CATCH-B`, areas, and runoff coefficients |
| Scenarios | A synthetic 10-year design event and 100-year major event |
| Basin | Bottom and crest levels plus linearly varying plan area |
| Outlet | One controlled orifice and one emergency weir |
| Network | Two ordered full-pipe reaches, two pits, and an outfall |
| Criteria | Release, velocity, HGL, freeboard, continuity, and numeric tolerances |

Changing section contents changes every downstream hash. Changing revision metadata alone changes the source-state, package, and run identities while preserving the content and calculation-input hashes.

## Calculation boundary

For each declared scenario, the kernel:

1. Calculates each catchment's peak runoff using the Rational Method.
2. Builds a fixed-step triangular inflow hydrograph.
3. Routes that inflow through a level-pool basin using a linearly varying stage-storage area.
4. Calculates head-dependent orifice flow and a tailwater-reduced sharp-crested emergency-weir flow. The weir uses the dimensionless-coefficient form `2/3 x Cd x sqrt(2g) x L x H^1.5`; downstream HGL reduces the available head.
5. Iterates the orifice head against the downstream network HGL.
6. Calculates full-pipe velocity, Manning capacity, friction loss, and minor loss through the two-pipe chain.
7. Records every time step, maximum storage and water level, freeboard, HGL, velocities, outlet flows, spill, convergence, and mass balance.

The time step, iteration limit, equations, criteria, and tolerances are fixed and content-bound. Routing retains full precision. Criteria are evaluated against the same canonical six-decimal result values that are serialized, so the producer and verifier cannot disagree at a rounding boundary.

## Identity chain

```text
revisioned source sections
  -> source-state SHA-256
  -> calculation-input SHA-256
  -> immutable package SHA-256
  + exact artifact-producing source inventory
  + exact Python patch and Pydantic runtime identity
  + selected scenario
  -> run request and run ID
  -> results, time series, and report hashes
  -> run manifest

sealed run manifest
  + exact verifier source inventory
  -> separate verification result bound to the manifest SHA-256
```

The identity-bearing files contain no timestamps, absolute paths, or random IDs. Repeating the same run in another directory under the same recorded runtime produces the same package, request, and run bytes.

The fixed-byte golden commitment uses CPython 3.13.2 with Pydantic 2.11.10. `.python-version` and the Linux workflow pin that canonical evidence runtime. Other Python versions allowed by the library remain supported, but they intentionally produce a different runtime identity; they run the functional and repeated-run determinism tests without being compared to the 3.13.2 byte fixture.

The package and run reject symlinks, unexpected files, missing files, overlapping output paths, stale requests, modified source state, and artifact hash drift. Publication is staged, filesystem-synced, and atomically renamed into place.

## Verifier boundary

The verifier is separate from run publication and does not trust the report or its stored pass flags. It:

1. Checks the exact package file set and hashes.
2. Validates all typed source contracts and section hashes.
3. Rebuilds the expected run request from the immutable package.
4. Checks every run artifact hash.
5. Reruns the hydraulic calculation from source state using the exact content-bound kernel recorded by the request.
6. Compares the complete numeric result and time series.
7. Regenerates and compares the report bytes.
8. Derives criteria independently from the numeric results and hashed source criteria.
9. Confirms the run's reported criteria match the verifier's derivation.

This is independent verification of the stored evidence, not a second hydraulic solver. Correctness is additionally anchored by hand-calculated primitive tests, a closed-form two-step coupled-routing oracle, event-volume checks, high-tailwater invariants, source-sensitivity tests, and an isolated negative fixture for every physical gate.

## Commands

List the public worlds:

```bash
uv run aec-bench --json task hydraulic-world list
```

Materialize an immutable package:

```bash
uv run aec-bench --json task hydraulic-world materialize \
  ssc03.public.detention-network.v1 \
  --output /tmp/ssc03-hydraulic-package
```

Run one declared scenario outside the package:

```bash
uv run aec-bench --json task hydraulic-world run \
  /tmp/ssc03-hydraulic-package \
  --scenario major-100yr \
  --output /tmp/ssc03-hydraulic-run
```

Verify the immutable evidence:

```bash
uv run aec-bench --json task hydraulic-world verify \
  /tmp/ssc03-hydraulic-package \
  /tmp/ssc03-hydraulic-run
```

The installed-CLI end-to-end test runs these commands from outside the repository.

## Run artifacts

Each run contains:

| File | Purpose |
| --- | --- |
| `request.json` | Exact world, scenario, package, source, calculation, and engine identity |
| `results.json` | Canonical engineering summary and source-reported criteria |
| `timeseries.json` | Every fixed hydraulic time step |
| `report.md` | Human-readable source-bound engineering report |
| `run-manifest.json` | SHA-256 for every other run artifact |

The `verify` command emits the verifier gates and exact verifier source inventory separately. Verifier changes therefore do not change an already sealed computation run or reuse its run ID for different run bytes.

## Provisional engineering rulings

These are synthetic benchmark rulings, not project design approvals:

- The 30-minute design event must remain below the emergency-weir crest and keep total structured release at or below `0.42 m3/s`.
- The two-hour major event must exercise the emergency weir, retain at least `0.30 m` freeboard, avoid uncontrolled spill, and stay within pipe velocity, capacity, and HGL-clearance limits.
- Tailwater reduces both orifice and weir head. Positive outlet flow is not accepted when the receiving HGL reaches or exceeds the basin water surface.
- Exact parameter values create a controlled public fixture with observable pass and failure margins. They are not proposed as generally applicable drainage criteria.

## What PR18 still does not add

PR18 deliberately adds no model-facing hydraulic tool. A model cannot yet request a hydrology run, alter outlet geometry, or select a tailwater boundary through the lifecycle.

That is PR19's job. PR19 can wrap the model-independent `build_hydraulic_run_request` and `execute_hydraulic_world` seam in the PR17 action protocol. Each future action must bind the visible source-state hash and publish the resulting immutable run evidence through host-owned state transitions.

PR18 also provides no model-performance evidence, public calibration run, private holdout, transfer claim, post-training result, or continual learning.
