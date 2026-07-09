# ABOUTME: Future verifier contract for the SSC-13 road visual operations source pack.
# ABOUTME: Keeps implementation acceptance criteria concrete without adding runtime code.

# SSC-13 Road Visual Operations Verifier Implementation Brief

This is a docs-only implementation brief for future benchmark hardening. It is not executable verifier code, not a generated benchmark instance, and not an issued lighting, ITS, CCTV, communications, or traffic-control design report.

The future verifier should treat `road_visual_operations_source_pack` as a closed task-owned source pack. It should grade against embedded files only, not live lighting software, online standards text, manufacturer tools, or external camera calculators.

## Inputs

The verifier should read:

- `project.json` for pack identity, unit system, scene summary, source-policy boundary, and data-file inventory.
- `source-index.md` for task-owned versus external workflow-reference boundaries.
- `lighting_comms_source_manifest.yaml` for shared SSC-13 source fields, thresholds, cases, device IDs, topology, power, and authority partitions.
- `scene-layout.csv` for road, luminaire, CCTV, VMS, cabinet, switch, and fibre object identities.
- `lighting-grid-results.csv` for point-by-point lighting values.
- `device-schedule.csv` for device roles, power, network load, and PoE load.
- `camera-coverage-oracle.csv` for target widths, horizontal pixels, PPM, bitrate, retention, storage, and status.
- `network-power-oracle.csv` for expected summary rows.
- `case-ledger.yaml`, `handoff-ledger.yaml`, and `stage-graph.yaml` for source-case and handoff continuity.
- `verification-rules.yaml` and `verification-cases.yaml` for gate definitions and localized failures.
- `expected-output.md` for memo/table requirements.

## Stage Contract

The verifier should produce one structured result per stage:

1. `source_intake`: all required files exist, parse, and preserve task-owned source status.
2. `object_identity`: every scheduled device can be traced to a scene object or declared cabinet-contained component.
3. `lighting_summary`: average, minimum, and min/average uniformity recompute from `lighting-grid-results.csv`.
4. `lighting_thresholds`: lighting pass/fail rows match the manifest thresholds.
5. `cctv_coverage`: PPM recomputes from horizontal pixels and target width.
6. `cctv_storage`: storage recomputes from bitrate, retention, and overhead.
7. `vms_policy`: message policy ID, allowed messages, and non-claim boundary are preserved.
8. `network_power`: bandwidth, PoE, fibre loss, and UPS energy recompute from source files.
9. `handoff_trace`: values in `handoff-ledger.yaml` match source tables and are consumed by the expected memo.
10. `memo_traceability`: solver output names source files, source status, object IDs, values, pass/fail rows, and unresolved limits.
11. `source_policy`: solver output does not claim external live software runs, full standards compliance, accepted project status, or benchmark readiness.

## Diagnostics

Each failed check should report:

- `stage`: one of the failure-localization values in `verification-cases.yaml`;
- `source_file`: the source-pack file that failed or created the mismatch;
- `row_id`: the device, grid, camera, network, handoff, or case identifier where applicable;
- `expected`: the recomputed or source-pack value;
- `actual`: the solver-supplied or parsed value;
- `message`: a concise root-cause explanation suitable for benchmark feedback.

Diagnostics should preserve root cause. For example, a camera target-width error should fail at `cctv_coverage`, not later as a generic memo error unless the coverage table is correct and the memo mutates the value.

## Acceptance Evidence

Current package-contract evidence exists for:

- a `road-visual-operations-package` entry in the `CompositeTaskWorldTemplate` catalogue;
- a materialized example containing `template.json`, `world.json`, hidden state, structured example answer, deliverable file, and verifier result;
- a package-contract verifier pass that checks source references, handoff presence, branch decisions, deliverable manifest entries, and gate evidence.

Before this pack is treated as benchmark-ready, future implementation should also leave evidence for:

- baseline pass result using the unmodified seed pack;
- negative-case failures for manifest, object identity, lighting, CCTV PPM, CCTV storage, VMS policy, traffic-control non-claim, bandwidth, PoE, fibre loss, UPS energy, memo mutation, and readiness overclaim cases;
- source-pack parser checks that recompute lighting, CCTV, bandwidth, PoE, fibre, and UPS rows from the fixture files;
- a fixture-generation or runtime packaging manifest showing how the source pack imports into generated benchmark instances.

Until that evidence exists, this pack remains a runnable package-contract example and source-pack design material rather than a completed benchmark fixture.
