# ABOUTME: Real and near-real artifact examples for PV storage feeder package grounding.
# ABOUTME: Identifies public inputs, outputs, reports, and fixture candidates for benchmark design.

# PV Storage Feeder Package Artifact Examples

## Public Artifacts Found

| Artifact | Source | Input/Output Shape | Benchmark Use |
| --- | --- | --- | --- |
| PVWatts V8 API documentation | https://developer.nrel.gov/docs/solar/pvwatts/v8/ | Request parameters, ranges, response fields, JSON/XML examples, monthly and hourly outputs. | Excellent structured fixture source for PV production. |
| PVWatts calculator | https://pvwatts.nrel.gov/ | User-facing PV production inputs and outputs. | Human-facing input/output analogue. |
| SAM | https://sam.nrel.gov/ | PV and storage techno-economic modelling. | Higher-fidelity model source and storage variants. |
| REopt API V3 and repository | https://developer.nrel.gov/docs/energy-optimization/reopt/v3/ and https://github.com/NREL/REopt_API | Optimization request/response surface for PV, storage, generator, tariff, outage, emissions, resilience, cost, and dispatch fields. | Excellent fixture path for PV+BESS sizing/dispatch tasks that sit between PVWatts production and feeder/interconnection checks. |
| GreenEVT / SMART-DS / OpenDSS testbed | https://arxiv.org/abs/2305.12722 and https://github.com/GreenEVT/GreenEVT | Synthetic distribution feeder data, buses, lines, transformers, loads, voltage/current limits, time-series loads, OpenDSS simulations, geospatial coupling to parcels/transport. | Feeder/load-profile substrate for composite PV/storage/EV/feeder tasks; repository file inspection now gives concrete fixture conventions. |
| GreenEVT OpenDSS folder conventions | https://github.com/GreenEVT/GreenEVT/blob/main/data/open_dss/README.txt | `Master.dss`, `Buscoords.dss`, `bus_info.csv`, `Long_lat_buscoords.txt`, substation/subtransmission network data, analysis folder, and per-feeder `Load.dss` variants. | Strong candidate for benchmark source-pack layout and verifier expectations. |
| GreenEVT OpenDSS solver workflow | https://github.com/GreenEVT/GreenEVT/blob/main/scripts/solve_opendss.py | SQLite `Vehicles` table, scenario id, bus charging counts, working `Loads.dss`, compiled `Master.dss`, solved circuit, timestamped overload CSV exports. | Useful model-world pattern for feeder stress, EV/PV/BESS scenario mutation, and structured output checking. |
| NFPA 70/NEC Article 690 metadata | https://www.nfpa.org/codes-and-standards/nfpa-70-standard-development/70 | Code authority metadata; full text gated. | Electrical compliance source identity. |
| IEEE 1547 metadata | https://standards.ieee.org/ieee/1547/5915/ | DER interconnection and interoperability scope covering performance, operation, testing, safety, maintenance, abnormal conditions, power quality, islanding, commissioning, and periodic testing. | Authority-basis metadata for DER interconnection tasks; detailed criteria should be task-supplied or licensed. |
| IEC 62548-1 metadata | https://webstore.iec.ch/en/publication/64171 | PV array design scope covering DC wiring, protection, switching, earthing, final PCE, and battery-connected PV-array protection considerations. | International authority-basis metadata for PV array/source-circuit checks; detailed criteria should be task-supplied or licensed. |
| Energy Networks Australia DER grid-connection guidelines | https://www.energynetworks.com.au/resources/guidelines/national-distributed-energy-resources-grid-connection-guidelines/ | Technical studies, commissioning evidence, SLD requirements, protection/control schematics, static DER data, export limits, inverter settings, and storage capacity fields. | Strong public schema source for Australian DNSP-style interconnection source packs. |
| PG&E Electric Rule 21 tariff | https://www.pge.com/tariffs/assets/pdf/tariffbook/ELEC_RULES_21.pdf | Export/non-export screens, single-line diagram definition, PCS export-control options, commissioning testing, expedited non-export battery-storage requirements, application/form catalog. | Strong US utility source for export-basis, SLD completeness, equipment, control, and commissioning verifier stages. |
| CEC Solar Equipment Lists | https://www.energy.ca.gov/programs-and-topics/programs/solar-equipment-lists | Public lists for PV modules, grid-support inverters, batteries, ESS, meters, PCS, and V2G equipment, plus listing request/instruction surfaces. | Equipment eligibility and smart-inverter/PCS list-check fixture source. |

## Fixture Candidates

- PVWatts JSON request/response pair with system capacity, module type, losses, array type, tilt, azimuth, lat/lon, and monthly AC/DC outputs.
- REopt request/response pair with load profile, tariff, PV/BESS/generator candidates, resilience or cost objective, selected capacity, dispatch schedule, NPV/cost/emissions/resilience outputs, and constraint evidence.
- OpenDSS feeder case with `Master.dss`, bus coordinate file, bus table, feeder load files, load profile/vehicle charging database, PV production CSV, and battery dispatch table.
- ENA-style interconnection source pack with SLD, connection point, PCC, EG/PV/BESS units, loads, meters, breakers, isolators, protection/control schematic, static DER register fields, export limits, inverter settings, and commissioning checklist.
- Rule 21-style export-basis pack with non-export/limited-export option, PCS response basis, manufacturer data sheets, control-system description, SLD details, commissioning functions, and operating profile where required.
- CEC/equipment-list check pack with PV modules, inverters, battery/ESS, meter, PCS functionality, listing status, and authority-specific smart-inverter requirement note.
- Single-line diagram with inverter, BESS, feeder, breaker, conductor, metering points, voltage/current limit evidence, export-control boundary, and protection devices.
- Cable schedule and voltage-drop/ampacity table.

## Remaining Artifact Need

- Public accepted PV+BESS SLDs and interconnection applications.
- Utility feeder-study outputs, settings tables, and accepted export-limitation examples beyond generic rules.
- Feeder sizing examples under NEC, IEC, and AS/NZS bases.
- Local extraction of a small GreenEVT/SMART-DS subset, including Git LFS or ZIP-managed files, before relying on it as a redistributable benchmark fixture.
