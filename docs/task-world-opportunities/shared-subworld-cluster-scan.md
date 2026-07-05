# ABOUTME: Exhaustive shared-subworld cluster scan over all task-world opportunity cards.
# ABOUTME: Ranks corpus-derived cross-discipline clusters using the non-traditional composition rubric.

# Shared-Subworld Cluster Scan

This report is the exhaustive follow-up to `non-traditional-composition-threads.md`. It scans all task cards in `task-catalogue.csv`, assigns each card to one primary shared-subworld cluster and up to two secondary clusters, then ranks the resulting clusters with the shared-subworld rubric.

## Method

- Input corpus: `184` task cards from `task-catalogue.csv`.
- Coverage check: `184/184` cards received a primary shared-subworld cluster.
- Matching basis: task name, discipline, category, description, standards, tags, modality families, and hidden-parameter fields from the catalogue. The task-card Markdown files remain the human evidence layer, but the exhaustive cluster assignment is driven from the normalized catalogue so repeated boilerplate does not dominate.
- Cluster shape: 19 physical/product shared-subworld clusters plus one standards/authority overlay cluster.
- Output tables: `shared-subworld-cluster-scan.csv` for ranked clusters and `shared-subworld-card-membership.csv` for per-card memberships.

The classifier is intentionally heuristic. It is strong enough for research triage and weak enough that a future source-pack pass must still inspect the named cards and detailed passes before claiming benchmark readiness.

## Rubric

Each physical cluster is scored out of 30:

| Axis | Meaning |
| --- | --- |
| shared_subworld_concreteness | Whether the cluster has a concrete source surface such as a profile, SLD, borehole log, layout, schedule, curve, or operating record. |
| cross_discipline_distance | How many disciplines appear in the assigned card set, with single-discipline clusters penalized. |
| verifier_locality | Whether failures can be localized to source extraction, invariant preservation, handoff, branch decision, or final calculation. |
| source_pack_realism | Whether ordinary project/source packs would contain the needed artifacts. |
| event_value | Whether contradictions would teach the meta-harness a useful new distinction. |
| stage_substrate | Whether enough existing cards support meaningful staged products. |

## Ranked Clusters

| Rank | Cluster | Score | Cards | Primary | Disciplines | Candidate Product | Main Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | SSC-07 Ground investigation, groundwater, and soil/resistivity world | 30 | 22 | 17 | civil;electrical;ground;structural | Soil and groundwater as both structural stability and electrical safety medium | Soil strength and soil resistivity are adjacent but not interchangeable; authority partition is critical. |
| 2 | SSC-01 Road/corridor profile and traffic scene | 29 | 18 | 9 | civil;electrical;mechanical | Road low-point drainage and field equipment resilience | Needs a profile/drainage/equipment source pack without overclaiming full flood modelling. |
| 3 | SSC-14 Structural load, support, foundation, and connection world | 28 | 46 | 17 | civil;electrical;ground;mechanical;structural | Cross-discipline support/foundation package for pipe, facade, equipment, and retaining loads | Very powerful but broad; must pick one physical support/foundation layout. |
| 4 | SSC-11 Piping network, transient, thrust, and support world | 28 | 35 | 11 | civil;electrical;ground;mechanical;structural | Pipe transient to support/foundation and protection-trip package | Transient event definition and support/foundation geometry must be source-owned. |
| 5 | SSC-03 Stormwater catchment, drainage, and hydraulic grade world | 27 | 35 | 17 | civil;mechanical | Drainage network plus downstream pump/equipment or road low-point package | Can collapse into natural civil drainage unless joined to a non-civil shared surface. |
| 6 | SSC-17 Energy resource, storage, resilience, and operating time-series world | 27 | 62 | 13 | civil;electrical;mechanical;structural | Energy resilience product joining PV/BESS, biogas, critical load, and feeder assumptions | Strong but can duplicate PV-storage unless treatment/process or resilience surface is explicit. |
| 7 | SSC-06 Equipment layout, motor schedule, and duty-point world | 27 | 64 | 11 | civil;electrical;mechanical;structural | Pump/blower duty to electrical load, acoustic impact, support/foundation package | Needs actual curve/datasheet or task-owned equipment schedule to avoid handwavey selection. |
| 8 | SSC-10 Process wastewater, treatment, and plant energy world | 27 | 15 | 11 | civil;electrical;mechanical | Wastewater energy island: process loads, biogas, PV/BESS, feeder | Mostly process/mechanical until electrical load or energy schedule evidence is added. |
| 9 | SSC-05 Electrical SLD, feeder, load, and protection world | 26 | 48 | 14 | electrical | Feeder/SLD shared subworld for BESS, pump, fire, PoE, and arc-flash products | Many tasks are electrical-only unless a mechanical/civil equipment schedule is included. |
| 10 | SSC-02 Rail corridor profile, signalling, and OLE | 26 | 12 | 10 | civil;electrical;mechanical | Rail weather, OLE sag, signal sighting, braking, and drainage clearance | Operator standards and sighting/STOPDIST evidence are harder to source publicly. |
| 11 | SSC-19 Fire, hazard, suppression, and tenability world | 26 | 11 | 8 | civil;electrical;mechanical | BESS/fire/hazard package or fire-water/structural-fire/arc-flash safety product | Standards and accepted calculation evidence are high-risk; public data may be sparse. |
| 12 | SSC-09 Roof/facade/envelope wind, drainage, and fixing world | 26 | 16 | 2 | civil;electrical;structural | Roof/facade/PV wind, drainage, access tolerance, and fixing package | Needs geometry ownership so wind, drainage, and fixing zones do not drift. |

## Exhaustive Cluster Index

| Cluster | Shared Subworld | Score | Memberships | Primary Cards | Disciplines | Top Task Cards |
| --- | --- | --- | --- | --- | --- | --- |
| SSC-07 Ground investigation, groundwater, and soil/resistivity world | borehole/CPT/SPT logs, groundwater record, soil profile, resistivity/grounding test area | 30 | 22 | 17 | civil;electrical;ground;structural | exit-gradient, fos-rapid-drawdown, fos-seismic, fos-steady-state, lateral-earth-pressure, retaining-wall-stability, solar-array-wind-load, uplift-pressure, wave-breaking, grid-resistance |
| SSC-01 Road/corridor profile and traffic scene | road vertical profile, chainage, crossfall, road speed, intersections, roadside equipment | 29 | 18 | 9 | civil;electrical;mechanical | curve-elements, design-wind-pressure, driveway-gradient-check, intersection-sight-distance, min-curve-radius, ssd-on-grade, superelevation-rate, all-red-interval-calculation, bandwidth-calculation, handling-capacity |
| SSC-14 Structural load, support, foundation, and connection world | load schedule, support layout, foundation plan, connection/bracket/member schedule, material actions | 28 | 46 | 17 | civil;electrical;ground;mechanical;structural | design-wind-pressure, design-wind-speed, exit-gradient, fos-rapid-drawdown, fos-seismic, fos-steady-state, hudson-armor-sizing, lateral-earth-pressure, pipe-invert-calculation, retaining-wall-stability |
| SSC-11 Piping network, transient, thrust, and support world | P&ID/pipe alignment, supports, restraints, transient event, thrust block/foundation interfaces | 28 | 35 | 11 | civil;electrical;ground;mechanical;structural | darcy-weisbach-headloss, exit-gradient, flap-gate-headloss, fos-rapid-drawdown, fos-seismic, fos-steady-state, hazen-williams-headloss, hgl-check, lateral-earth-pressure, linear-wave-theory |
| SSC-03 Stormwater catchment, drainage, and hydraulic grade world | catchment plan, rainfall/time-series, drainage long section, pits, pipes, detention/outfall structures | 27 | 35 | 17 | civil;mechanical | culvert-capacity, darcy-weisbach-headloss, detention-volume-preliminary, downpipe-sizing, flap-gate-headloss, gutter-sizing, hazen-williams-headloss, hgl-check, mannings-pipe-capacity, open-channel-capacity |
| SSC-17 Energy resource, storage, resilience, and operating time-series world | solar/weather/load/gas/energy records, BESS/PV, biogas, critical load/autonomy, operating profile | 27 | 62 | 13 | civil;electrical;mechanical;structural | culvert-capacity, detention-volume-preliminary, downpipe-sizing, flap-gate-headloss, freeboard-calculation, gutter-sizing, hgl-check, mannings-pipe-capacity, open-channel-capacity, orifice-outlet-design |
| SSC-06 Equipment layout, motor schedule, and duty-point world | equipment layout, pump/blower/compressor/motor schedule, duty point, equipment datasheet/curve | 27 | 64 | 11 | civil;electrical;mechanical;structural | bund-volume-calculation, cerc-longshore-transport, curve-elements, darcy-weisbach-headloss, hazen-williams-headloss, hudson-armor-sizing, linear-wave-theory, min-curve-radius, npsh-calculation, pipe-velocity-check |
| SSC-10 Process wastewater, treatment, and plant energy world | process basis, PFD, influent/effluent samples, basin schedules, aeration/sludge/biogas records | 27 | 15 | 11 | civil;electrical;mechanical | pump-power-calc, 4-20ma-scaling, biogas-production, chemical-dosing, cstr-volume, hrt-calculation, mass-balance, mlss-inventory, nitrification-srt, oxygen-requirements |
| SSC-05 Electrical SLD, feeder, load, and protection world | single-line diagram, load schedule, feeder/cable identity, fault/protection basis, switchboard geometry | 26 | 48 | 14 | electrical | ac-resistance-temperature, access-controller-sizing, all-red-interval-calculation, bandwidth-calculation, battery-sizing, bess-sizing, bess-sizing-basic, busbar-forces, cable-ampacity, car-dimensions-check |
| SSC-02 Rail corridor profile, signalling, and OLE | rail route profile, chainage, gradient, speed, signal layout, OLE span/weather envelope | 26 | 12 | 10 | civil;electrical;mechanical | cant-calculation, driveway-gradient-check, thermal-stress-calculation, transition-spiral-length, vertical-curve-design, overlap-calculation, power-load-calculation, signal-sighting-distance, single-span-sag-tension, warning-time-calculation |
| SSC-19 Fire, hazard, suppression, and tenability world | fire strategy, sprinkler/hydrant/supply, design fire/visibility/steel temperature, hazardous inventory | 26 | 11 | 8 | civil;electrical;mechanical | bund-volume-calculation, incident-energy, available-flow-calculation, elevation-pressure, friction-loss-hazen-williams, nac-load-calculation, sprinkler-discharge, steel-critical-temp, t-squared-hrr, visibility-criterion |
| SSC-09 Roof/facade/envelope wind, drainage, and fixing world | roof/facade geometry, pressure zones, PV/racking layout, gutters/downpipes, brackets/tolerances | 26 | 16 | 2 | civil;electrical;structural | design-wind-pressure, design-wind-speed, downpipe-sizing, gutter-sizing, roadway-spread, sls-load-combinations, solar-array-wind-load, uls-load-combinations, ice-load-calculation, wind-load-conductor |
| SSC-04 Coastal, flood, wave, and marine boundary world | coastal profile, tide/SLR table, wave climate, runup/freeboard, outfall/asset level | 25 | 13 | 9 | civil;mechanical;structural | cerc-longshore-transport, freeboard-calculation, hudson-armor-sizing, linear-wave-theory, outfall-submergence-check, tidal-prism, wave-breaking, wave-runup, wave-shoaling, slr-calculation |
| SSC-08 Building occupancy, room, egress, and vertical movement world | floor/room plan, occupancy/population schedule, egress route, lift/escalator group, fire alarm zones | 25 | 20 | 7 | electrical;mechanical | access-controller-sizing, all-red-interval-calculation, car-dimensions-check, cctv-storage-calculation, escalator-capacity, handling-capacity, interval-calculation, lux-level-calculation, ppm-calculation, shaft-dimensions |
| SSC-15 Material/product compliance and certificate world | mill/product certificate, material chemistry, mix design, product datasheet, code compliance note | 24 | 14 | 6 | civil;electrical;mechanical;structural | driveway-gradient-check, pipe-velocity-check, sewer-slope-check, ac-resistance-temperature, busbar-forces, voltage-drop, occupant-load, por-aor-compliance, steel-critical-temp, carbon-equivalent-calc |
| SSC-13 Lighting, visual performance, ITS, CCTV, and communications scene | road/room/field lighting grid, CCTV coverage, VMS/message library, topology and bandwidth/power | 23 | 18 | 12 | electrical | bandwidth-calculation, cctv-storage-calculation, conduit-fill-calculation, fiber-link-loss-budget, interior-uniformity, leni-calculation, lux-level-calculation, overlap-calculation, poe-power-budget, ppm-calculation |
| SSC-16 Construction, temporary works, environmental controls, and staging world | construction staging plan, erosion/sediment controls, temporary traffic/comms/power, site monitoring | 23 | 8 | 2 | civil;electrical;structural | bund-volume-calculation, cerc-longshore-transport, design-wind-speed, freeboard-calculation, pollutant-load-estimate, sediment-basin-sizing, string-sizing, construction-tolerance |
| SSC-12 Acoustic, vibration, and receiver-impact world | equipment noise/vibration schedule, source map, receiver plan, octave spectra, operating scenario | 19 | 6 | 6 | mechanical | a-weighting, distance-attenuation, miner-fatigue, sabine-rt60, spl-log-sum, vibration-transmissibility |
| SSC-18 Instrumentation, controls, valve, and process signal world | P&ID, loop schedule, valve datasheet, 4-20 mA range, control/protection settings | 15 | 2 | 2 | electrical | cv-liquid-incompressible, 4-20ma-scaling |
| SSC-20 Regional standards, authority, and review packet overlay | standard/owner/AHJ criteria, permits, forms, design report package, source authority gates | overlay | 0 | 0 |  |  |

## What Changed From The Hand-Curated Map

- The earlier map identified strong examples. This scan confirms the broader corpus can support the same move: every task card can be projected into at least one shared-subworld cluster.
- Some high-scoring clusters are broad substrate clusters, especially equipment/duty-point, structural support/foundation, electrical SLD/feeder, and energy time-series. They are useful as join surfaces but should be narrowed before source-pack hardening.
- The current best next hardening target remains road low-point drainage and field equipment resilience. It is not the highest raw-card-count cluster, but it scores strongly because the shared subworld is concrete and the verifier events are crisp: chainage/datum drift, grade-sign mismatch, HGL/surface mismatch, and equipment-clearance overclaiming.
- The soil/groundwater structural-electrical cluster is the strongest philosophical follow-up because it tests whether one physical site can appear under two authority regimes without collapsing soil strength into electrical resistivity.

## Recommended Next Source-Pack Targets

1. `SSC-01` plus `SSC-03` plus `SSC-05`: road low-point drainage and field equipment resilience.
2. `SSC-07` plus `SSC-05` plus `SSC-14`: soil/groundwater as both structural stability and electrical safety medium.
3. `SSC-05` plus `SSC-17` plus `SSC-19`: BESS fire, containment, ventilation, feeder, and protection package.
4. `SSC-10` plus `SSC-06` plus `SSC-12`: wastewater blower process, power, and acoustic impact package.
5. `SSC-08` plus `SSC-13` plus `SSC-19`: station population, vertical movement, egress, alarm, ventilation, and visual operations package.

The practical next step is to pick one target and define a `shared_subworld_manifest`: source artifacts, invariants, authority partitions, scalar handoff contracts, conflict ledger, and repair events.

The full per-cluster follow-up design pack is captured in `shared-subworld-designs/`. It applies the standalone SSC-17 output shape to all 19 physical/product clusters plus the SSC-20 authority overlay: evidence basis, set-style frame, shared-subworld manifest, eight concrete product-world candidates, per-product source-pack and variant tables, cross-product composition, verifier events, hardening order, operationalization addendum, and explicit non-claims. The original SSC-17 standalone follow-up is preserved in `ssc-17-energy-resilience-long-horizon-design.md`.
