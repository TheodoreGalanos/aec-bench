# ABOUTME: Gap register for the PV storage feeder package.
# ABOUTME: Tracks missing standards access, real artifacts, and follow-up research questions.

# PV Storage Feeder Package Gaps

## Source Gaps

- NEC Article 690, IEEE 1547, IEC 62548-1, AS/NZS 5033, AS/NZS 4777, and AS/NZS 5139 full criteria are gated or restricted even though public metadata confirms the authority family.
- ENA guidelines and PG&E Rule 21 now define strong interconnection package shape, but accepted utility applications, filled SLD packages, protection settings, and feeder-study results are still missing.
- Need clear public examples for PV+BESS cable sizing, voltage-drop calculations, export-control settings, and PCS operating-profile evidence.
- Need utility-specific examples beyond California/PG&E and Australian ENA-style guidance before generalizing rule behavior across authorities.

## Data Gaps

- Real interval load data is often sensitive.
- SMART-DS/GreenEVT-style synthetic feeder data may be acceptable for benchmarks. Repository inspection confirms useful OpenDSS conventions, but local extraction of Git LFS/ZIP-managed data and redistribution hygiene still need verification.
- Public single-line diagrams are often generic and omit cable lengths or settings.
- SAM project files and PVWatts result files are accessible in principle but need curated examples.
- REopt request/response fixtures are accessible in principle but still need curated examples aligned with PVWatts production, tariff/load data, and downstream feeder constraints.
- CEC equipment-list data gives an eligibility-check surface, but fixture design needs captured list extracts or stable task-owned excerpts for modules, inverters, ESS, batteries, meters, and PCS functionality.
- Need a deliberately small GreenEVT/OpenDSS subset that can be run quickly in CI or benchmark harness mode without requiring the full Greensboro dataset.

## Benchmark Gaps

- Need code-basis metadata on every task instance.
- Need separation between production model verification and compliance/rubric verification.
- Need structured handling of load profiles so tasks can pass between PV, feeder, and protection packages.
- Need staged verifier contracts for PVWatts production, REopt optimization/dispatch, SLD/interconnection completeness, equipment-list eligibility, export-control basis, OpenDSS feeder study, and commissioning evidence.
- Need task-owned excerpts for detailed standards and utility criteria so model performance does not depend on memorized gated standards.
