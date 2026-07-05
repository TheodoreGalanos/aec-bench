# ABOUTME: Indexes the per-cluster long-horizon design pack.
# ABOUTME: Points from each scan cluster to its engineering packages, variants, checks, and hardening route.

# Shared-Subworld Long-Horizon Design Pack

This directory applies the SSC-17 design process to every identified cluster in `shared-subworld-cluster-scan.md`: 19 physical/product clusters plus the SSC-20 regional standards/authority overlay.

Each detailed design note now starts from ordinary engineering work packages and then records the structure needed for future source files, checks, and verifier design:

- evidence basis from the cluster scan;
- plain-language card descriptions and engineering data fields;
- eight concrete cluster-specific work packages;
- a short engineering description, task-card anchors, source-file shape, variants, and best-use note for every package;
- composition pattern across variants;
- checks worth designing for;
- recommended hardening order and source-pack build notes;
- explicit non-claims.

Machine-readable coverage is in `design-manifest.csv`. Each row records eight product families, 40 variant rows, eight manifest fields, and 10 verifier-event rows for the corresponding cluster note.

The first three domain-practice grounding batches plus the SSC-13, SSC-16, SSC-12, and SSC-18 single-note passes are now marked in `design-manifest.csv` with `domain_practice_notes=yes`. The covered clusters are `SSC-07`, `SSC-01`, `SSC-14`, `SSC-11`, `SSC-03`, `SSC-17`, `SSC-06`, `SSC-10`, `SSC-05`, `SSC-02`, `SSC-19`, `SSC-09`, `SSC-04`, `SSC-08`, `SSC-15`, `SSC-13`, `SSC-16`, `SSC-12`, and `SSC-18`; each now has a short `Domain Practice Notes` section covering real-world fit, typical practitioner steps, current software stack anchors, and design implications. One cluster note still needs that same web-backed practice layer: `SSC-20`.

Runnable-template operationalization is now tracked separately in `../real-world-grounding/runnable-template-catalogue.md`. Nineteen of the 19 physical/product SSC notes have one runnable template: `SSC-07`, `SSC-01`, `SSC-14`, `SSC-11`, `SSC-03`, `SSC-17`, `SSC-06`, `SSC-10`, `SSC-05`, `SSC-02`, `SSC-19`, `SSC-09`, `SSC-04`, `SSC-08`, `SSC-15`, `SSC-13`, `SSC-16`, `SSC-12`, and `SSC-18`. No physical/product SSC notes remain in this runnable-template stream; `SSC-20` is excluded because it is a regional standards and authority overlay rather than a physical/product cluster.

All-product runnable expansion is tracked separately in `../real-world-grounding/product-expansion-catalogue.md`. All 19 physical/product SSC notes now have runnable synthetic examples for all eight product families; no physical/product note remains in this stream. `SSC-20` remains excluded as a regional standards and authority overlay.

## Cluster Design Index

| Cluster | World | Score | Cards | Design Note | First Hardening Candidate | Main Risk |
| --- | --- | --- | --- | --- | --- | --- |
| SSC-07 | Ground investigation, groundwater, and soil/resistivity world | 30 | 22 | [ssc-07-ground-investigation-groundwater-and-resistivity-long-horizon-design.md](ssc-07-ground-investigation-groundwater-and-resistivity-long-horizon-design.md) | Soil and groundwater structural-electrical safety package | Soil strength and soil resistivity are adjacent but not interchangeable; authority partition is critical. |
| SSC-01 | Road/corridor profile and traffic scene | 29 | 18 | [ssc-01-road-corridor-profile-long-horizon-design.md](ssc-01-road-corridor-profile-long-horizon-design.md) | Road low-point drainage and field equipment resilience | Needs a profile/drainage/equipment source pack without overclaiming full flood modelling. |
| SSC-14 | Structural load, support, foundation, and connection world | 28 | 46 | [ssc-14-structural-load-support-foundation-connection-long-horizon-design.md](ssc-14-structural-load-support-foundation-connection-long-horizon-design.md) | Pipe transient support and foundation package | Very powerful but broad; must pick one physical support/foundation layout. |
| SSC-11 | Piping network, transient, thrust, and support world | 28 | 35 | [ssc-11-piping-network-transient-thrust-and-support-long-horizon-design.md](ssc-11-piping-network-transient-thrust-and-support-long-horizon-design.md) | Pump transient, thrust, support, and protection-trip package | Transient event definition and support/foundation geometry must be source-owned. |
| SSC-03 | Stormwater catchment, drainage, and hydraulic grade world | 27 | 35 | [ssc-03-stormwater-drainage-and-hgl-long-horizon-design.md](ssc-03-stormwater-drainage-and-hgl-long-horizon-design.md) | Detention and outlet design-check package | Can collapse into natural civil drainage unless joined to a non-civil shared surface. |
| SSC-17 | Energy resource, storage, resilience, and operating time-series world | 27 | 62 | [ssc-17-energy-resource-storage-resilience-operating-time-series-long-horizon-design.md](ssc-17-energy-resource-storage-resilience-operating-time-series-long-horizon-design.md) | Stormwater controls and pumping outage resilience | Strong but can duplicate PV-storage unless treatment/process or resilience surface is explicit. |
| SSC-06 | Equipment layout, motor schedule, and duty-point world | 27 | 64 | [ssc-06-equipment-layout-motor-schedule-and-duty-point-long-horizon-design.md](ssc-06-equipment-layout-motor-schedule-and-duty-point-long-horizon-design.md) | Pump station duty, power, NPSH, and feeder package | Needs actual curve/datasheet or task-owned equipment schedule to avoid handwavey selection. |
| SSC-10 | Process wastewater, treatment, and plant energy world | 27 | 15 | [ssc-10-process-wastewater-treatment-and-plant-energy-long-horizon-design.md](ssc-10-process-wastewater-treatment-and-plant-energy-long-horizon-design.md) | Wastewater energy island | Mostly process/mechanical until electrical load or energy schedule evidence is added. |
| SSC-05 | Electrical SLD, feeder, load, and protection world | 26 | 48 | [ssc-05-electrical-sld-feeder-and-protection-long-horizon-design.md](ssc-05-electrical-sld-feeder-and-protection-long-horizon-design.md) | Mechanical-load to feeder and voltage package | Many tasks are electrical-only unless a mechanical/civil equipment schedule is included. |
| SSC-02 | Rail corridor profile, signalling, and OLE | 26 | 12 | [ssc-02-rail-corridor-profile-long-horizon-design.md](ssc-02-rail-corridor-profile-long-horizon-design.md) | Level crossing warning-time and backup-power package | Operator standards and sighting/STOPDIST evidence are harder to source publicly. |
| SSC-19 | Fire, hazard, suppression, and tenability world | 26 | 11 | [ssc-19-fire-hazard-suppression-tenability-long-horizon-design.md](ssc-19-fire-hazard-suppression-tenability-long-horizon-design.md) | Fire-water, sprinkler demand, and storage hazard package | Standards and accepted calculation evidence are high-risk; public data may be sparse. |
| SSC-09 | Roof/facade/envelope wind, drainage, and fixing world | 26 | 16 | [ssc-09-roof-facade-envelope-wind-drainage-fixing-long-horizon-design.md](ssc-09-roof-facade-envelope-wind-drainage-fixing-long-horizon-design.md) | Facade wind, bracket, anchor, and tolerance package | Needs geometry ownership so wind, drainage, and fixing zones do not drift. |
| SSC-04 | Coastal, flood, wave, and marine boundary world | 25 | 13 | [ssc-04-coastal-flood-and-marine-boundary-long-horizon-design.md](ssc-04-coastal-flood-and-marine-boundary-long-horizon-design.md) | Coastal flood, outfall, pump, and electrical elevation package | Datum and planning-horizon control must be explicit before joining assets. |
| SSC-08 | Building occupancy, room, egress, and vertical movement world | 25 | 20 | [ssc-08-building-occupancy-room-egress-vertical-movement-long-horizon-design.md](ssc-08-building-occupancy-room-egress-vertical-movement-long-horizon-design.md) | Station population, vertical movement, egress, alarm, and ventilation package | Can become too broad unless scoped to one floor/zone and scenario. |
| SSC-15 | Material/product compliance and certificate world | 24 | 14 | [ssc-15-material-product-compliance-and-certificate-long-horizon-design.md](ssc-15-material-product-compliance-and-certificate-long-horizon-design.md) | Product submittal review packet overlay | Often evidence assembly rather than long-horizon physical composition. |
| SSC-13 | Lighting, visual performance, ITS, CCTV, and communications scene | 23 | 18 | [ssc-13-lighting-visual-its-cctv-communications-long-horizon-design.md](ssc-13-lighting-visual-its-cctv-communications-long-horizon-design.md) | Road visual operations, ITS, CCTV, lighting, and comms power package | Needs a concrete scene/layout, otherwise it is a loose collection of devices. |
| SSC-16 | Construction, temporary works, environmental controls, and staging world | 23 | 8 | [ssc-16-construction-temporary-works-environmental-controls-staging-long-horizon-design.md](ssc-16-construction-temporary-works-environmental-controls-staging-long-horizon-design.md) | Construction environmental controls, temporary traffic, and monitoring power package | Temporary works artifacts vary widely and can become scenario prose without drawings. |
| SSC-12 | Acoustic, vibration, and receiver-impact world | 19 | 6 | [ssc-12-acoustic-vibration-and-receiver-impact-long-horizon-design.md](ssc-12-acoustic-vibration-and-receiver-impact-long-horizon-design.md) | Blower or pump duty to acoustic impact package | Small current card substrate unless joined to equipment and site layout clusters. |
| SSC-18 | Instrumentation, controls, valve, and process signal world | 15 | 2 | [ssc-18-instrumentation-controls-valve-process-signal-long-horizon-design.md](ssc-18-instrumentation-controls-valve-process-signal-long-horizon-design.md) | Valve Cv, process value, and signal scaling package | Current catalogue substrate is thin; likely a follow-up after process/piping worlds. |
| SSC-20 | Regional standards, authority, and review packet overlay | 0 | 0 | [ssc-20-regional-standards-authority-review-overlay-long-horizon-design.md](ssc-20-regional-standards-authority-review-overlay-long-horizon-design.md) | Regional standards overlay for any shared-subworld product | Overlay only; not ranked as a physical product cluster. |

## Cross-Cluster Hardening Themes

| Theme | Clusters | Practical Use |
| --- | --- | --- |
| Road and drainage operational resilience | SSC-01, SSC-03, SSC-05, SSC-13, SSC-17 | Build source packs where a profile, storm event, field equipment, power, and communications share one scene. |
| Ground, support, and electrical safety | SSC-07, SSC-14, SSC-05, SSC-20 | Keep geotechnical strength, groundwater, resistivity, foundation, and authority evidence partitioned. |
| Process, equipment, energy, and impact | SSC-10, SSC-06, SSC-12, SSC-17, SSC-18 | Join process duty to equipment selection, power, acoustics, and controls. |
| Fire, hazard, emergency, and building operations | SSC-19, SSC-08, SSC-05, SSC-17, SSC-20 | Separate normal loads from emergency modes and authority gates. |
| Envelope, coastal, and weather-exposed assets | SSC-09, SSC-04, SSC-14, SSC-17, SSC-20 | Preserve geometry, datum, weather, supports, drainage, and resilience assumptions. |
| Evidence and review packet integrity | SSC-15, SSC-20 plus every physical cluster | Turn certificates, standards, submission requirements, comments, and source policy into verifier gates. |

## Recommended Portfolio Starts

1. `SSC-01` + `SSC-03` + `SSC-17`: road low-point drainage and field equipment energy resilience.
2. `SSC-07` + `SSC-14` + `SSC-05`: soil/groundwater as structural and electrical safety medium.
3. `SSC-10` + `SSC-06` + `SSC-12` + `SSC-17`: wastewater process, blower power, acoustic impact, and energy island.
4. `SSC-19` + `SSC-05` + `SSC-17`: BESS/fire/hazard, containment, ventilation, feeder, and emergency operation.
5. `SSC-08` + `SSC-13` + `SSC-19` + `SSC-17`: station population, visual operations, life safety, and emergency power.

These are detailed design-research artifacts. None of these notes claims source-pack hardening, executable verifier implementation, or benchmark readiness.
