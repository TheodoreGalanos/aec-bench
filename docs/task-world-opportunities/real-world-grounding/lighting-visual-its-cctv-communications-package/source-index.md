# ABOUTME: Source index for the SSC-13 lighting, visual, ITS, CCTV, and communications package.
# ABOUTME: Points to task-owned synthetic source-pack artifacts and external workflow references.

# Source Index

This package captures the SSC-13 road visual operations route as a runnable synthetic, task-owned example candidate. It is not an issued road-lighting, ITS, CCTV, or communications design report.

## Task-Owned Source Pack

| Source Pack | Status | Purpose |
| --- | --- | --- |
| `road_visual_operations_source_pack/` | docs-only runnable-synthetic seed | Defines one closed road visual operations scene with task-owned source tables, handoff ledgers, expected output, verifier rules, negative cases, and implementation guidance. |

## External Workflow References

These sources shape the fixture fields and output expectations. They are not grading sources for the task-owned baseline.

| Source | Role |
| --- | --- |
| [AGi32](https://lightinganalysts.com/agi32/) | Photometric calculation, point-by-point illuminance/luminance, CAD import, photometric data, and report-output workflow shape. |
| [DIALux road lighting](https://www.dialux.com/en-GB/street-lighting) | Road profile, lighting class, luminaire arrangement, evaluation field, grid table, isolux, and documentation workflow shape. |
| [FHWA current MUTCD](https://mutcd.fhwa.dot.gov/kno_11th_Editionr1.htm) | Current official route for U.S. traffic-control and changeable-message-sign source status. |
| [AXIS Site Designer](https://www.axis.com/support/tools/axis-site-designer) | CCTV placement, coverage, bandwidth, storage, power, bill-of-materials, and installer note workflow shape. |
| [JVSG IP Video System Design Tool](https://www.jvsg.com/ip-video-system-design-tool/) | Camera coverage, pixel-density, storage, and bandwidth design workflow shape. |
| [ARC-IT](https://www.arc-it.net/) | ITS architecture and communications-view workflow shape. |
| [NTCIP document list](https://www.ntcip.org/document-numbers-and-status/) | Device-profile and communications standards source route for DMS, CCTV, lighting management, Ethernet, and TCP/IP profiles. |

## Source Boundary

The source pack uses task-owned synthetic values. External sources justify the source fields and workflow shape only. A solver must not claim that the synthetic pack is an accepted project, a standards-compliant lighting design, an approved traffic-control plan, or a benchmark-ready executable fixture.
