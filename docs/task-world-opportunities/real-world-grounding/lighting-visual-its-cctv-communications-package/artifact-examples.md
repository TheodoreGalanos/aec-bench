# ABOUTME: Artifact examples for the SSC-13 road visual operations synthetic source pack.
# ABOUTME: Lists expected source files, outputs, and verifier-facing records.

# Artifact Examples

## Task-Owned Inputs

The first source-pack seed is `road_visual_operations_source_pack/`.

| Artifact | Role |
| --- | --- |
| `project.json` | Pack identity, unit system, fixture policy, and task-owned boundary. |
| `source-index.md` | Source authority and external workflow references. |
| `lighting_comms_source_manifest.yaml` | Scene, criteria, device, topology, power, and source fields all stages must reuse. |
| `scene-layout.csv` | Synthetic road, luminaire, camera, VMS, cabinet, and fibre objects. |
| `lighting-grid-results.csv` | Task-owned lighting grid values and lighting summary inputs. |
| `device-schedule.csv` | Device IDs, roles, power, network, and source status. |
| `camera-coverage-oracle.csv` | Camera target width, resolution, PPM, bitrate, retention, and pass/fail values. |
| `network-power-oracle.csv` | Bandwidth, PoE, fibre, lighting load, and UPS handoff oracle values. |
| `case-ledger.yaml` | Governing scene, lighting, CCTV, VMS, network, and power cases. |
| `handoff-ledger.yaml` | Named intermediate values consumed by downstream stages. |
| `stage-graph.yaml` | Ordered stages, consumed files, produced handoffs, and gate families. |
| `verification-rules.yaml` | Source, formula, handoff, memo, and non-claim rules. |
| `verification-cases.yaml` | Baseline pass plus localized negative cases. |
| `expected-output.md` | Required memo and table content for the agent response. |
| `verifier-implementation-brief.md` | Future executable verifier contract. |

## Expected Agent Output

A valid response should include:

- source-pack status and non-claim boundary;
- lighting summary table with average, minimum, and min/average uniformity;
- CCTV coverage and storage table;
- network, PoE, fibre, and backup-power table;
- pass/fail summary for each stage;
- visual operations memo naming the governing source values and unresolved limits.

It should not claim approved design status, full MUTCD compliance, photometric certification, public project evidence, executable verifier readiness, generated instances, or benchmark readiness.

## Runnable Package-Contract Example

`road-visual-operations-package` is now present in the composite task-world template catalogue. The existing materializer can generate a runnable package-contract example and the existing verifier can check source references, handoffs, branch decisions, deliverable manifest entries, and product-specific gate evidence.

That package-contract pass is not the same as source-pack formula verification. It does not yet parse `lighting-grid-results.csv`, `camera-coverage-oracle.csv`, `network-power-oracle.csv`, or the negative cases as executable source-pack checks.
