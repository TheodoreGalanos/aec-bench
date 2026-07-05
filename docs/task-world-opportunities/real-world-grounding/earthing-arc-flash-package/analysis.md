# ABOUTME: Analysis for grounding the earthing arc flash package in real workflows.
# ABOUTME: Summarizes workflow chain, inputs, outputs, benchmark implications, and multimodal scope.

# Earthing Arc Flash Package Analysis

## Real Workflow Chain

The chain is realistic:

single-line diagram -> equipment and source data -> short-circuit/fault current -> protective device clearing time -> earthing/touch-step voltage basis -> arc current and incident energy -> arc flash boundary/PPE label -> busbar/cable withstand note.

In practice, arc flash depends heavily on study setup and data collection. IEEE 1584 metadata explicitly points to hazard distance and incident energy models, while IEEE 1584.1 and 1584.2 are useful for specifying deliverables and collecting required study data.

The GLEAMM microgrid paper strongly supports the chain at report level: it starts from topology and source/equipment data, studies grid-connected and islanded operating modes, computes short-circuit currents by bus, applies IEEE 1584-style arc-flash parameters, and ends with equipment label fields.

OSHA 1910.269 Appendix C strengthens the public work-practice side of the earthing chain. It is not a grounding-grid design manual, but it gives public authority for ground-potential gradients, step/touch potentials, engineering analysis under fault conditions, equipotential zones, grounding grids or mats, and the relationship between protective grounding and fastest available clearing time.

IEEE 81-2025 adds a current public metadata anchor for the measurement side of grounding systems. It does not give open formula text, but it names the real measurement artifacts we should expect: earth-resistivity tests, ground impedance to remote earth, transient or surge impedance where relevant, touch/step-voltage measurements, grounding-system integrity checks, instrumentation limits, and measurement-distortion notes.

IEEE 1048-2016 adds a current protective-grounding authority path that sits naturally between OSHA Appendix C and utility practice. Its public metadata frames temporary protective grounding for de-energized overhead and underground transmission/distribution lines, cables, and equipment. The 1048b-2024 amendment metadata is especially useful for benchmark design because it names conductive mats as a specific equipotential-zone artifact.

IEEE DataPort's public arc-flash spreadsheet calculators add a second useful artifact shape: menu-style engineering inputs and tabular arcing-current/incident-energy outputs. They are not formula authority, and the page explicitly caveats their relationship to IEEE 1584-2018, but they are still useful for source-pack and verifier-interface design.

The authority-status side is now clearer. IEEE 1584-2018 is active and its public page points to 1584.1 for study scope/deliverable requirements and 1584.2-2025 for data-collection checklists. IEEE 80-2013 is inactive-reserved as of 2024-03-21, with active project P80 visible but no active replacement standard listed on the public page. For Australia/NZ high-voltage variants, AS 2067:2016 is current metadata for substations and high-voltage installations above 1 kV a.c., including visible contents for earthing systems, safety measures, protection/control systems, inspection/testing, and O&M manuals.

The utility-standard search boundary is also sharper. Ausgrid exposes a public technical document library for standards and guidelines, but direct NS116/earthing checks from this environment returned zero visible results and did not recover a stable document payload. ENA S34-style rise-of-earth-potential searches also kept returning secondary summaries rather than an official public copy. That means utility-specific earthing criteria should remain a data gap unless we obtain an authorized utility standard, project basis, or task-supplied excerpt.

## Real Inputs

- Single-line diagram, transformer data, utility contribution, generator/motor contribution, cable impedances, switchgear/enclosure data.
- Protective devices: type, settings, time-current curves, clearing time, maintenance mode, upstream/downstream coordination.
- Equipment voltage, working distance, enclosure type, conductor gap/configuration, grounding/bonding arrangement.
- Soil resistivity, ground impedance/resistance to remote earth, grid geometry, fault duration, split factor/current division, touch/step voltage criteria, surface-layer assumptions, and measurement distortion notes for earthing variants.
- Work-practice and temporary-grounding basis: equipotential-zone boundaries, conductive mats/grids, conductive objects to bond, grounding-grid/mat assumptions, restricted areas, and clearing-time assumptions for protective grounding.
- Applicable standard set: IEEE 1584/NFPA 70E/OSHA, IEC 60909/IEC 60479, IEEE 80/P80 status, AS 2067, regional utility standards.
- For microgrid/PV/BESS variants: operating topology, inverter/generator short-circuit contribution, source contribution factors, and mode-specific bus fault currents.

## Real Outputs

- Fault current table and protective-device clearing-time evidence, ideally tied to time-current curves or settings.
- Arc flash incident energy and boundary table.
- Equipment labels or label data: voltage, available incident energy, boundary, PPE/work practice basis.
- Earthing summary: soil resistivity interpretation, ground impedance/resistance, touch/step voltage, mesh voltage, conductor thermal withstand, measurement method, instrumentation limits, and inspection/testing basis where applicable.
- Work-practice/equipotential-zone note for OSHA-style variants: hazardous-potential analysis, bonded objects, grounding point, temporary ground path, restricted area, and protective-equipment assumptions.
- Assumption register and one-line diagram mark-up.
- Mode comparison table for grid-connected, islanded, backup-generator, or maintenance configurations where applicable.

## Harness Implications

- The task should be evidence-heavy. A scalar incident-energy answer is insufficient without fault current and clearing-time traceability.
- Strong failure modes include using bolted fault current as arc current without model adjustment, selecting wrong protective-device clearing time, ignoring enclosure/gap/working distance, and mixing earthing grid checks with arc flash without a clear shared fault basis.
- Some checks need standards-aware rubrics because exact IEEE/NFPA equations are gated.
- Spreadsheet calculator artifacts can support input/output schemas and regression-style fixtures, but the harness still needs explicit protection-device clearing times or curves to avoid grading a detached incident-energy calculation.
- OSHA Appendix C can support public work-practice/equipotential-zone variants, especially where the benchmark asks whether a grounding arrangement minimizes hazardous potential differences. It should not be used as a substitute for IEEE 80/P80 or AS 2067 grid-design acceptance criteria.
- IEEE 81-2025 supports measurement/commissioning fixture requirements: the verifier can check that soil resistivity, ground impedance, touch/step voltage, instrumentation, and distortion assumptions are all present, even when acceptance limits are supplied by the task or a gated standard.
- IEEE 1048-2016 and the 1048b-2024 amendment metadata support temporary-grounding/equipotential-zone fixtures: the verifier can separately check fastest-clearing-time reasoning, low-impedance grounding path, bonded conductive objects, conductive mat/grid use, and worker-zone boundaries.
- The GLEAMM paper shows the expected arc-duration field shape by tying arc duration to the slowest protective-device trip and then using a specific cycle duration in the study. A fixture-grade task still needs actual time-current curves or settings tied to the same SLD.
- For Australia/NZ variants, AS 2067 can establish the high-voltage installation/earthing authority basis, but deterministic grading still needs task-supplied acceptance criteria or licensed public-view details.
- A useful verifier split is now visible: arc-flash study completeness, protection-clearing traceability, and earthing/ground-grid safety should be checked as connected but distinct evidence contracts.

## Multimodal Extension

- Inputs: SLD image/PDF, protection coordination curve, equipment schedule, arc-flash label, cable schedule, ground grid drawing, soil-resistivity table.
- Outputs: annotated SLD, extracted device table, fault/clearing-time table, labels, and study memo.
- Interesting checks: OCR/diagram extraction of device hierarchy, curve-reading, label consistency, and propagation of source impedance changes through downstream equipment.

## Meta-Harness Opportunities

- Reconfigure study scope: arc flash only, earthing only, combined LV/MV protection study.
- Mutate protection settings, transformer size, feeder length, enclosure type, and maintenance mode.
- Combine with PV/storage by adding inverter/BESS contribution and revised SLD.
- Combine with treatment/pump packages by passing motor loads and MCC data downstream.
