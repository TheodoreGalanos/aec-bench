# ABOUTME: Real and near-real artifact examples for earthing arc flash package grounding.
# ABOUTME: Identifies public inputs, outputs, reports, and fixture candidates for benchmark design.

# Earthing Arc Flash Package Artifact Examples

## Public Artifacts Found

| Artifact | Source | Input/Output Shape | Benchmark Use |
| --- | --- | --- | --- |
| IEEE 1584-2018 page | https://standards.ieee.org/ieee/1584/5802/ | Arc-flash hazard calculation standard metadata, hazard distance and incident energy model description, and related study/data-collection standards. | Authority metadata for calculation basis and task deliverables. |
| IEEE 1584.1/1584.2 metadata | https://standards.ieee.org/ieee/1584/5802/ | Scope/deliverable and data collection checklist metadata. | Input/output contract guidance. |
| IEEE DataPort arc flash calculators | https://ieee-dataport.org/open-access/arc-flash-ie-and-iarc-calculators | Spreadsheet-style user inputs, equipment configuration choices, arcing-current outputs, incident-energy outputs, two calculator files, user manual, and documented caveats. | Calculator-like fixture model for source-pack design; not formula authority and not enough for protection-clearing evidence. |
| IEEE 80 metadata | https://standards.ieee.org/ieee/80/4089/ | AC substation grounding scope, substations covered, inactive-reserved status, 2024-03-21 inactivation date, active P80 project metadata, and no active replacement standard listed on the page. | Earthing/ground-grid authority metadata; P80 successor and worked examples still need follow-up. |
| IEEE 81-2025 metadata | https://standards.ieee.org/ieee/81/11218/ | Measurement scope for earth resistivity, ground impedance to remote earth, transient/surge impedance, touch/step voltages, grounding-system integrity, instrumentation limits, and measurement distortion. | Strong fixture contract for field-test/commissioning packets: test method, instrument, measured values, distortion notes, and acceptance basis. |
| IEEE 1048-2016 metadata | https://standards.ieee.org/standard/1048-2016.html | Temporary protective grounding scope for de-energized overhead/underground transmission and distribution lines, cables, and equipment; 1048a-2021 and 1048b-2024 amendments listed, with 1048b naming conductive mats for equipotential zones. | Work-practice and protective-grounding fixture model, especially when combined with OSHA Appendix C. |
| Standards Australia AS 2067 metadata | https://store.standards.org.au/product/as-2067-2016 | Current metadata for high-voltage installations above 1 kV a.c.; visible contents include earthing systems, safety measures, protection/control/auxiliary systems, inspection/testing, and operation/maintenance manual. | Australia/NZ regional authority basis for high-voltage installation and earthing variants; exact criteria are gated. |
| Ausgrid technical document library search boundary | https://www.ausgrid.com.au/asp-and-contractors/technical-document-library?q=NS116 | Public catalogue page for technical standards and guidelines; direct NS116/earthing searches showed zero visible server-rendered results from this environment. | Negative-result artifact: NSW utility earthing standards should be treated as not captured until an authorized document or task-supplied excerpt is available. |
| OSHA electrical safety topic | https://www.osha.gov/electrical | Hazard framing, arc flash focus, grounding/protective-device controls. | Safety and work-practice context. |
| OSHA 1910.269 Appendix C | https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.269AppC | Ground-potential gradient, step/touch potential, engineering analysis, equipotential zone, grounding grid/mat, bonded conductive objects, restricted area, and fastest available clearing-time principles. | Public work-practice fixture path for earthing/equipotential-zone variants; not a substitute for IEEE 80/P80 grid-design calculations. |
| Short Circuit and Arc Flash Study on a Microgrid Facility | https://arxiv.org/abs/2105.09927 and https://arxiv.org/pdf/2105.09927 | Real microgrid topology, source and cable data, transformer parameters, operating topologies, fault-current tables, arcing current, incident energy, boundary, PPE category, and label fields. | Strong report-shaped fixture model for SLD-to-study-to-label tasks, although the one-line diagram image itself still needs visual extraction handling. |
| IEC 60909 open implementation paper | https://arxiv.org/abs/1802.01502 | Grid element data, fault-current calculation workflow, distributed generation contribution, open-source pandapower implementation. | Fault-current fixture path for arc-flash and protection variants. |

## Fixture Candidates

- Single-line diagram with transformer, switchboard, MCC, feeders, motors, utility/source contribution, distributed generation, battery/inverter contribution, and device hierarchy.
- Protection settings and time-current curves, especially clearing times for each bus or protective-device zone.
- Source table, cable table, transformer table, fault current table, clearing-time table, incident-energy table, and label dataset.
- Ground grid drawing/soil resistivity table for earthing variants.
- IEEE 81-style field-test fixture with soil-resistivity readings, ground impedance/resistance measurement setup, touch/step-voltage readings, instrumentation, test-current/source details, and measurement-distortion notes.
- OSHA/IEEE 1048-style work-practice fixture with energized object, grounding point, bonded conductive objects, conductive mat or grounding grid, equipotential-zone boundary, restricted area, and clearing-time assumption.
- High-voltage installation metadata pack for Australia/NZ variants: AS 2067 authority basis, earthing-system section reference, protection/control basis, inspection/testing basis, and task-supplied criteria.

## Remaining Artifact Need

- Public SLD/protection datasets that can be redistributed; the GLEAMM paper gives tables and figures but not an immediately reusable machine-readable dataset.
- IEEE P80 successor publication/status, IEC grounding authority metadata, AS 2067 public-view details, utility-specific earthing standards, and accessible earthing examples.
- Real arc-flash labels and study reports with enough data to reproduce calculations.
- Redistributable protection time-current curves or clearing-time tables linked to the same SLD as the arc-flash study.
- Grounding-grid calculation examples with soil resistivity, grid geometry, split factor/current division, grid resistance, touch voltage, step voltage, and mesh voltage.
