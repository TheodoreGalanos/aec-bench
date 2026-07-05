# ABOUTME: Source index for the SSC-13 road visual operations source-pack seed.
# ABOUTME: Separates task-owned grading files from external workflow references.

# Road Visual Operations Source Index

This pack is a task-owned synthetic source pack for `SSC-13-LH-01`. It is not an issued design report, accepted project packet, software export, or authority approval.

## Task-Owned Grading Sources

| File | Source Type | Authority Role | Use |
| --- | --- | --- | --- |
| `project.json` | pack metadata | fixture policy | Establishes ID, units, scene, and non-claim boundary. |
| `lighting_comms_source_manifest.yaml` | source manifest | fixture source of truth | Defines shared source fields and source-status partitions. |
| `scene-layout.csv` | object schedule | fixture source of truth | Names road, luminaire, camera, VMS, cabinet, and fibre objects. |
| `lighting-grid-results.csv` | calculation oracle | fixture source of truth | Provides grid values used for average/minimum/uniformity checks. |
| `device-schedule.csv` | device register | fixture source of truth | Provides installed device IDs, roles, power, bandwidth, and source status. |
| `camera-coverage-oracle.csv` | calculation oracle | fixture source of truth | Provides PPM, bitrate, retention, and storage values. |
| `network-power-oracle.csv` | calculation oracle | fixture source of truth | Provides bandwidth, PoE, fibre, lighting-load, and UPS handoff values. |
| `case-ledger.yaml` | case ledger | fixture source of truth | Records governing scenario and selected criteria. |
| `handoff-ledger.yaml` | handoff ledger | fixture source of truth | Names intermediate values and downstream consumers. |
| `stage-graph.yaml` | stage graph | fixture source of truth | Records ordered checks, inputs, handoffs, and gate families. |
| `verification-rules.yaml` | verifier rule plan | future verifier contract | Defines deterministic checks and tolerances. |
| `verification-cases.yaml` | verifier case plan | future verifier contract | Defines baseline and negative cases. |
| `expected-output.md` | response contract | future verifier contract | Defines the required memo and tables. |
| `verifier-implementation-brief.md` | implementation contract | future verifier contract | Defines future parser and verifier acceptance evidence. |

## External Workflow References

| Source | Source Status | How It Informs This Pack |
| --- | --- | --- |
| AGi32 product page | external workflow reference | Photometric calculation, CAD/source geometry, photometric data, maps, reports. |
| DIALux road-lighting page | external workflow reference | Road profile, lighting class, evaluation fields, grid tables, isolux charts. |
| FHWA MUTCD current-edition page | external official source route | Current official traffic-control source status and PDF route. |
| AXIS Site Designer page | external workflow reference | CCTV placement, coverage, bandwidth, storage, power, bill of materials. |
| JVSG IP Video System Design Tool page | external workflow reference | CCTV pixel-density, bandwidth, and storage workflow route. |
| ARC-IT | external workflow reference | ITS architecture and communications-view route. |
| NTCIP document list | external standards route | DMS, CCTV control, lighting management, Ethernet, and TCP/IP profile route. |

The baseline verifier should grade only the task-owned files above.
