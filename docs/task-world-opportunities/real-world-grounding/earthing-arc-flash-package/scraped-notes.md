# ABOUTME: Source-bounded notes for the earthing arc flash package.
# ABOUTME: Preserves short evidence notes without copying full manuals or standards.

# Earthing Arc Flash Package Scraped Notes

## IEEE 1584-2018 Standard Page

- IEEE identifies IEEE 1584-2018 as the active guide for performing arc-flash hazard calculations.
- The public description says it provides mathematical models for hazard distance and incident energy exposure.
- The page lists IEEE 1584.1-2022 for scope and deliverable requirements.
- The page lists IEEE 1584.2-2025 for data collection checklists for systems at 1000 V and below.
- The IEEE 1584 project metadata narrows scope to three-phase AC equipment in the 208 V to 15 kV range and excludes single-phase AC, DC, protection coordination studies, and PPE recommendations.
- The IEEE page links to open-access spreadsheet calculators on IEEE DataPort, which can inform fixture input/output shape but should not be treated as the standard text.

## IEEE DataPort Arc Flash Calculator Artifact

- The IEEE DataPort page describes spreadsheet calculators for incident energy and arcing current.
- The dataset metadata identifies spreadsheet format, equipment-configuration choices, user-entered inputs, and returned outputs.
- The page says the spreadsheets are not part of IEEE 1584-2018 and were not developed by the P1584 working group.
- The page lists two spreadsheet files and a user manual; it says open-access dataset files are available to logged-in users with a free IEEE account and IEEE membership is not required.
- The page discussion notes that reduced arcing current can affect protection tripping time and incident energy, reinforcing that clearing-time evidence is not optional.
- This is useful for harness engineering because it shows a realistic calculator-like source artifact: menu choices, engineering inputs, constants, and tabular outputs.
- It does not replace protection-device clearing-time evidence, coordination curves, or the full standard procedure.

## OSHA Electrical Topic Page

- OSHA frames electrical work as hazardous due to shock, electrocution, fires, and explosions.
- The page calls out arc flash as a focus area and links to arc-flash hazard resources.
- OSHA lists possible controls such as insulation, guarding, grounding, electrical protective devices, and safe work practices.

## OSHA 1910.269 Appendix C

- OSHA Appendix C to 1910.269 is a public regulatory appendix on protection from hazardous differences in electric potential.
- It explains ground-potential gradients and step/touch potentials when grounded objects, structures, cranes, or lines become energized under fault conditions.
- The appendix says an employer can use engineering analysis under fault conditions to determine whether hazardous step and touch voltages will develop.
- It identifies equipotential zones, insulating equipment, and restricted work areas as protection methods for workers on the ground.
- It defines a ground mat/grounding grid as a metallic mat or grating that establishes an equipotential surface and connection points for grounds.
- For temporary protective grounding, it states two useful benchmark principles: the grounding method should help the circuit open in the fastest available clearing time, and it should minimize potential differences between conductive objects in the work area.
- This source is strong public work-practice and safety evidence. It does not replace IEEE 80/P80 or AS 2067 for detailed substation grounding-grid design criteria.

## IEEE 1048-2016 Standard Page

- IEEE identifies IEEE 1048-2016 as an active guide for protective grounding of power lines.
- The public description covers temporary protective grounding for de-energized overhead and underground transmission and distribution lines, cables, and equipment.
- IEEE lists active amendments IEEE 1048a-2021 and IEEE 1048b-2024.
- IEEE 1048b metadata expands guidance for conductive mats used to establish an equipotential zone while applying temporary protective ground cables.
- This connects well to OSHA Appendix C: it strengthens protective-grounding and equipotential-zone source-pack shape, but not detailed substation grounding-grid design acceptance.

## IEEE 80-2013 Standard Page

- IEEE identifies IEEE 80-2013 as the Guide for Safety in AC Substation Grounding.
- The public page states that the guide is primarily concerned with outdoor AC substations, including distribution, transmission, and generating plant substations.
- The page notes that with proper caution the methods are also applicable to indoor portions of substations or wholly indoor substations.
- The page marks IEEE 80-2013 as inactive-reserved as of March 21, 2024.
- The same page lists active project P80 for AC substation grounding safety, describes its power-frequency substation grounding scope, and currently lists no active replacement standard.
- Future work should track P80 before hardening IEEE 80 as an active authority basis.

## IEEE 81-2025 Standard Page

- IEEE identifies IEEE 81-2025 as the active guide for measuring earth resistivity, ground impedance, and earth surface potentials of a grounding system.
- The public description frames it around practical test methods for grounding systems.
- Visible topics include grounding-system safety, earth-resistivity measurement, ground-system impedance to remote earth, transient and surge impedance, touch and step voltage, grounding-system integrity, instrumentation limits, and measurement distortion factors.
- IEEE marks IEEE 81-2025 as superseding IEEE 81-2012, with board approval on 2025-06-19 and publication on 2025-12-08.
- This is useful for field-test and commissioning artifacts. It does not supply open design acceptance calculations or a worked grounding-grid package.

## Standards Australia AS 2067 Metadata

- Standards Australia lists AS 2067:2016 as current, with the title "Substations and high voltage installations exceeding 1 kV a.c."
- The public payload says it provides minimum requirements for design and erection of high-voltage installations with nominal voltages above 1 kV a.c. and nominal frequency up to and including 60 Hz.
- The visible contents include scope/general, fundamental requirements, insulation, equipment, installations, safety measures, protection/control/auxiliary systems, earthing systems, inspection/testing, and operation/maintenance manual.
- This improves the Australia/NZ high-voltage installation and earthing authority metadata, but detailed earthing criteria remain standards-controlled.

## Microgrid Arc Flash Study

- The paper frames arc flash as a major hazard when operating electrical facilities.
- It states that equipment labels display short-circuit and arc-flash levels plus minimum PPE level.
- The paper develops complete modelling of a real microgrid testbed facility to perform short-circuit and arc-flash studies with the goal of labelling devices accessed by researchers.
- The worked sequence is directly useful for the task chain: data collection, operating topologies, three-phase bolted fault current, arcing current and incident energy, PPE category, and equipment labelling.
- The study uses a real microgrid with utility, diesel generator, wind turbines, solar plant, load banks, basic loads, and an Outback battery/inverter system.
- It exposes concrete electrical inputs: transformer ratings and impedances, line distances/cable types/impedances, source short-circuit contributions, operating topology, bus voltages, electrode configuration, conductor gap, working distance, enclosure size, and arc duration.
- It exposes concrete outputs: bus-level one-phase and three-phase short-circuit currents, arcing current, incident energy, arc-flash boundary, PPE hazard category, and label fields.
- The PDF makes the study sequence explicit: data collection, operating topologies, three-phase bolted fault currents, arcing current and incident energy, PPE category, and equipment labelling.
- The arc-flash section notes that arc duration should come from the slowest tripping protective device. The study then uses a five-cycle duration and reports bus-level bolted fault current, arcing current, incident energy, arc-flash boundary, and PPE category in a results table.
- This strengthens the protection-clearing side enough to show the expected field shape, but it still does not provide reusable time-current curves or actual relay/breaker setting curves for fixture-grade grading.
- The report is unusually valuable because it connects a one-line/topology artifact to numeric tables and then to final labels, which is the same evidence path a benchmark verifier should demand.

## Search Note On Protection And Grounding Fixtures

- Targeted public discovery for clean protection-coordination curve fixtures and grounding-grid worked examples did not produce a redistributable artifact suitable for promotion in this pass.
- OSHA Appendix C improved public grounding/work-practice authority, and the GLEAMM paper improved arc-duration field shape, but clean time-current curves, relay/breaker settings, soil-resistivity tables, grid geometry, touch voltage, and step voltage examples remain priority fixture gaps.
- A later source pass improved the authority map through IEEE 81-2025 and IEEE 1048-2016/1048a/1048b, but it still did not recover a clean utility earthing standard, selected protection-curve package, or worked grounding-grid dataset.

## Ausgrid Technical Document Library Search Boundary

- Ausgrid's technical document library describes standards, guidelines, and procedures for maintaining and modifying network infrastructure.
- A direct route to the candidate NS116 PDF redirected to the technical library search interface rather than a stable public PDF.
- The server-rendered technical-library query did not expose a stable NS116 or earthing result from this environment.
- Direct fetch and app-bundle inspection found the technical-document listing widget, but did not recover a stable public criteria document.
- ENA S34/Rise of Earth Potential searches likewise did not recover an official public criteria source in this pass.
- The packet should not claim NSW utility earthing criteria are captured; use an authorised utility standard or task-supplied excerpt for benchmark grading.

## IEC 60909 Open Implementation Paper

- The paper describes short-circuit-current calculation as important for grid planning and protection-system design.
- It states that IEC 60909 provides guidelines for short-circuit calculations and is routinely applied in grid-planning applications.
- The paper implements IEC 60909-style short-circuit calculation in pandapower and validates it against commercial software and examples from literature.
- The paper describes grid inputs such as lines, transformers, loads, external grids, generators, switches, and nameplate data.
