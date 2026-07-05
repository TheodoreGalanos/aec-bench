# ABOUTME: Source index for earthing arc flash package grounding.
# ABOUTME: Tracks fault, earthing, protection, incident energy, and safety standards.

# Earthing Arc Flash Package Source Index

## Current Chain Confidence

The chain is realistic:

single-line/fault study -> prospective fault current -> protection clearing time -> earthing/touch voltage -> incident energy and arc flash boundary -> busbar/mechanical force and cable withstand checks.

## Candidate Sources

| Source | Type | Region | Relevance |
| --- | --- | --- | --- |
| IEEE 1584-2018 standard page. https://standards.ieee.org/ieee/1584/5802/ | primary-gated metadata | Global | Official IEEE page for the guide for performing arc-flash hazard calculations. Public metadata describes mathematical models for hazard distance and incident energy, active status, related deliverable/data-collection standards, and an open-access calculator link. |
| IEEE 1584.1-2022 metadata on IEEE 1584 page. https://standards.ieee.org/ieee/1584/5802/ | primary-gated metadata | Global | Public metadata describes scope/deliverable requirements for arc-flash hazard calculation studies. Relevant to harness output contracts. |
| IEEE 1584.2-2025 metadata on IEEE 1584 page. https://standards.ieee.org/ieee/1584/5802/ | primary-gated metadata | Global | Public metadata describes data collection checklists for low-voltage arc-flash studies. Relevant to task input contracts. |
| IEEE DataPort Arc Flash IE and Iarc Calculators. https://ieee-dataport.org/open-access/arc-flash-ie-and-iarc-calculators | open-access dataset/tool artifact | Global | IEEE Standards Association spreadsheet calculators with equipment configurations, user inputs, arcing-current outputs, and incident-energy outputs. Explicitly not part of IEEE 1584-2018 and caveated, but useful for spreadsheet-style fixture shape. |
| IEEE 80-2013 standard page. https://standards.ieee.org/ieee/80/4089/ | primary-gated metadata/current-status | Global | Official IEEE page for the Guide for Safety in AC Substation Grounding. Public metadata says it is primarily concerned with outdoor AC substations and includes distribution, transmission, and generating plant substations. The page marks IEEE 80-2013 inactive-reserved, gives an inactivation date of 2024-03-21, and points to active project P80 with no active replacement standard yet listed. |
| IEEE 81-2025 standard page. https://standards.ieee.org/ieee/81/11218/ | primary-gated metadata/current | Global | Active IEEE guide for measuring earth resistivity, ground impedance, and earth surface potentials of grounding systems. Public metadata covers safety considerations, earth resistivity, ground-system impedance to remote earth, transient/surge impedance, touch and step voltage measurement, grounding-system integrity checks, instrumentation limits, and factors that distort measurements. Useful for source-pack fields and verification/commissioning variants rather than design acceptance criteria. |
| IEEE 1048-2016 standard page. https://standards.ieee.org/standard/1048-2016.html | primary-gated metadata/current | Global/US utility practice | Active IEEE guide for protective grounding of power lines. Public metadata covers temporary protective grounding of de-energized overhead/underground transmission and distribution lines, cables, and equipment. The page lists amendments 1048a-2021 and 1048b-2024; 1048b expands guidance on conductive mats for equipotential zones. Useful bridge between OSHA work-practice evidence and benchmark fixtures for protective-grounding/equipotential-zone variants. |
| Standards Australia, AS 2067:2016 Substations and high voltage installations exceeding 1 kV a.c. https://store.standards.org.au/product/as-2067-2016 | primary-gated metadata/current | Australia/NZ | Current Australian standard metadata. Public payload says it provides minimum requirements for design and erection of high-voltage installations above 1 kV a.c. and up to 60 Hz. Visible contents include fundamental requirements, equipment, safety measures, protection/control/auxiliary systems, earthing systems, inspection/testing, and operation/maintenance manual. |
| Ausgrid technical document library. https://www.ausgrid.com.au/asp-and-contractors/technical-document-library?q=NS116 | primary-open catalogue/dead-end | Australia/NSW | Ausgrid's public library states that its standards and guidelines govern maintaining or modifying network infrastructure. Direct checks for NS116/earthing routed to the library but showed zero server-rendered results from this environment, and bundle inspection did not recover a stable public document result. Useful as an access-boundary note for NSW utility earthing standards, not as a captured criterion source. |
| IEEE Std 80 public summaries. https://en.wikipedia.org/wiki/IEEE_P80 | secondary | Global | Orientation source for AC substation grounding safety, grid conductors, rods, fault current dissipation, and touch-voltage concern. |
| OSHA Electrical safety topic. https://www.osha.gov/electrical | government | US | Public OSHA page identifies arc flash as a focus and frames electrical hazards including shock, electrocution, fires, explosions, grounding, protective devices, and safe work practices. |
| OSHA 1910.269 Appendix C, Protection From Hazardous Differences in Electric Potential. https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.269AppC | government/regulatory appendix | US | Public work-practice authority for step/touch potential, ground-potential gradients, equipotential zones, grounding grids/mats, engineering analysis under fault conditions, and the principle of fastest available clearing time for protective grounding. It supports earthing safety evidence, but not detailed IEEE 80/P80 grid design calculations. |
| NFPA 70E standard page. https://www.nfpa.org/codes-and-standards/nfpa-70e-standard-development/70e | primary-gated | US/global influence | Work-practice and PPE authority; public page exposes little text through current access path, full standard text gated. |
| Schmitt et al., Short Circuit and Arc Flash Study on a Microgrid Facility. https://arxiv.org/abs/2105.09927 | academic/example-artifact | US/global | Real report-shaped source describing complete modelling of a microgrid testbed facility to perform short-circuit and arc-flash studies and label devices accessed by researchers. |
| Thurner and Braun, Vectorized Calculation of Short Circuit Currents Considering Distributed Generation. https://arxiv.org/abs/1802.01502 | academic/example-artifact | EU/global | Open-source IEC 60909 implementation paper. Useful for fault-current workflow, input model structure, distributed generation contribution, and potential fixture generation. |
| Arc flash public summary. https://en.wikipedia.org/wiki/Arc_flash | secondary | Global | Orientation on arc flash hazards, standards, PPE, incident energy, and NFPA/IEEE/OSHA ecosystem. |

## Gaps

- Find real public arc-flash study inputs/outputs: SLD, fault currents, protection clearing times, equipment data, labels.
- Find earthing/grid calculation examples with soil resistivity, grid resistance, current division, touch/step voltage, mesh voltage, and measurement/commissioning records.
- Clarify regional differences: IEEE/NFPA/OSHA, IEC 60909, IEC 60479, AS 2067, ENA/AS/NZS grounding practice, and utility-specific public criteria.
