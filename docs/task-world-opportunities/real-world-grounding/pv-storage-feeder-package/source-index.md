# ABOUTME: Source index for PV storage feeder package grounding.
# ABOUTME: Tracks PV, storage, feeder, code, and modelling sources.

# PV Storage Feeder Package Source Index

## Current Chain Confidence

The chain is realistic:

load profile -> PV array/string/inverter sizing -> DC/AC ratio -> usable storage and dispatch -> interconnection/export basis -> feeder voltage drop/ampacity/power-flow checks -> equipment eligibility and commissioning note.

PV production is strongly grounded by PVWatts/SAM, and PV+BESS sizing/dispatch can be grounded by REopt. Feeder and load-profile structure is grounded by OpenDSS/SMART-DS-style testbeds. DER interconnection, export limitation, commissioning, and equipment-list checks are now better grounded by IEEE 1547, IEC 62548-1, Energy Networks Australia DER connection guidelines, PG&E Rule 21, and California Energy Commission equipment-list evidence. The remaining weakness is accepted project-grade PV+BESS single-line diagrams, utility application packages, and a locally extracted redistributable feeder fixture.

## Candidate Sources

| Source | Type | Region | Relevance |
| --- | --- | --- | --- |
| NREL PVWatts. https://pvwatts.nrel.gov/ | primary-open | US/global | Public PV performance tool; visible inputs include DC system size, module type, array type, losses, tilt, azimuth, DC/AC ratio, inverter efficiency, albedo, and results such as solar radiation and AC energy. |
| PVWatts V8 API. https://developer.nrel.gov/docs/solar/pvwatts/v8/ | primary-open/example-artifact | US/global | Public API documentation with required request parameters, ranges, response fields, and JSON/XML examples. Strong source for machine-readable benchmark I/O. The current docs note a developer domain transition from `developer.nrel.gov` to `developer.nlr.gov`. |
| NREL SAM. https://sam.nrel.gov/ | primary-open | US/global | Public techno-economic modelling tool for PV and battery storage; covers front-of-meter and behind-the-meter storage. |
| NREL REopt API V3. https://developer.nrel.gov/docs/energy-optimization/reopt/v3/ | primary-open/example-artifact | US/global | Public optimization API for PV, storage, generators, resilience, emissions, and cost objectives; useful for task instances where PVWatts production feeds PV+BESS sizing and dispatch optimization. |
| NREL/National Renewable Energy Laboratory REopt API repository. https://github.com/NREL/REopt_API | primary-open/tool | US/global | Open-source API layer around REopt.jl. README describes a MILP-based model for optimal mixes of renewable energy, conventional generation, and storage with NPV and dispatch outputs. |
| GreenEVT: Greensboro Electric Vehicle Testbed. https://arxiv.org/abs/2305.12722 and https://arxiv.org/pdf/2305.12722 | academic/example-artifact | US | Open-source testbed description using OpenDSS, SUMO, SMART-DS distribution models, OpenStreetMap, parcels, and EV charging. Useful for feeder/load-profile artifact shape and multimodal/geospatial composition. |
| GreenEVT GitHub repository. https://github.com/GreenEVT/GreenEVT | example-artifact | US | Repository named by the GreenEVT paper. README identifies the project, MIT license, Git LFS use, and fallback ZIP download. Folders include `data`, `scripts`, `demoscripts`, and `wikimedia`. |
| GreenEVT OpenDSS data README. https://github.com/GreenEVT/GreenEVT/blob/main/data/open_dss/README.txt | example-artifact | US | Confirms fixture-level OpenDSS file conventions: `Master.dss`, `Buscoords.dss`, `bus_info.csv`, `Long_lat_buscoords.txt`, per-substation/subtransmission network data, analysis folder, and multiple feeder `Load.dss` files for EV penetration scenarios. |
| GreenEVT OpenDSS solver script. https://github.com/GreenEVT/GreenEVT/blob/main/scripts/solve_opendss.py | example-artifact | US | Shows how a SQLite `Vehicles` table is converted into timestamped bus EV charging counts, how `Loads_original.dss` becomes working `Loads.dss`, how `Master.dss` is compiled, and how timestamped overload CSV reports are exported. |
| NREL SMART-DS project, as described in GreenEVT. | example-artifact | US | Synthetic but realistic distribution networks down to households, with buses, lines, transformers, loads, voltage/current limits, peak planning loads, and yearly time-series loads. Useful substitute when real utility feeder data is sensitive. |
| OpenDSS, as used in GreenEVT. https://sourceforge.net/projects/electricdss/ | primary-open/tool | US/global | Distribution-system simulator used to compile electric networks, run unbalanced power-flow simulations, export network data, modify components, execute time simulations, and print solution reports. |
| NFPA 70 / NEC Article 690. https://www.nfpa.org/codes-and-standards/nfpa-70-standard-development/70 | primary-gated | US | Electrical code authority for PV installations; public landing page accessible but full article text gated. |
| IEEE 1547-2018. https://standards.ieee.org/ieee/1547/5915/ | primary-gated/metadata | US/global | DER interconnection and interoperability authority. Public metadata covers performance, operation, testing, safety, maintenance, abnormal conditions, power quality, islanding, commissioning, and periodic tests. |
| IEC 62548-1:2023. https://webstore.iec.ch/en/publication/64171 | primary-gated/metadata | International | PV array design requirements covering DC wiring, protection, switching, earthing, final power conversion equipment, and additional protection for PV arrays directly connected to batteries at DC level. Full criteria remain gated. |
| AS/NZS 5033 and AS/NZS 4777. | primary-gated/metadata | Australia/NZ | Regional PV array and inverter/grid connection standards. Official store metadata is accessible, but detailed criteria remain gated. |
| Energy Networks Australia National DER Grid Connection Guidelines. https://www.energynetworks.com.au/resources/guidelines/national-distributed-energy-resources-grid-connection-guidelines/ | primary-open/owner-guidance | Australia | Public DNSP-oriented connection-guideline source with technical studies, commissioning, SLD, protection/control schematic, static DER data, export-limit, inverter, storage, and settings evidence. Strong source-pack schema candidate. |
| PG&E Electric Rule 21. https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_RULES_21.pdf | primary-open/utility-tariff | US/California | Utility interconnection tariff for generating facilities. Local PDF inspection found definitions for single-line diagrams, export/non-export screens, non-export and limited-export PCS options, commissioning tests, and expedited non-export energy-storage requirements. |
| California Energy Commission Solar Equipment Lists. https://www.energy.ca.gov/programs-and-topics/programs/solar-equipment-lists | primary-open/equipment-list | US/California | Public equipment-list program for PV modules, grid-support inverters, batteries, ESS, meters, PCS, and related equipment. Useful for equipment eligibility, smart-inverter, battery/ESS, and PCS list-check subtasks. |

## Gaps

- Find accepted or anonymized PV+BESS single-line diagrams, interconnection applications, cable schedules, and voltage-drop calculations.
- Locally extract a small GreenEVT/SMART-DS/OpenDSS fixture subset and verify which Git LFS/ZIP files are needed for a redistributable benchmark fixture.
- Convert ENA/Rule 21/CEC fields into task-owned source-pack schemas for SLD completeness, export-control basis, equipment eligibility, static DER register data, commissioning, and feeder-study outputs.
- Preserve full-code criteria as task-supplied or licensed/public-view excerpts where NEC, IEC, IEEE, and AS/NZS clause text is gated.
