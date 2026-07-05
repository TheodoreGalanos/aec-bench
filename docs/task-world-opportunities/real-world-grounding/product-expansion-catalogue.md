# ABOUTME: Tracks runnable template coverage across every product in each SSC note.
# ABOUTME: Separates all-product synthetic examples from source-pack hardening and benchmark readiness.

# Product Expansion Catalogue

This catalogue tracks the second-pass expansion from one runnable template per physical/product SSC note to one runnable template per product family inside each note. It intentionally preserves the same boundary as the earlier runnable-template stream: these are task-owned synthetic examples unless a later source-pack hardening pass adds concrete source manifests, parser checks, provenance checks, and negative cases.

Current status: **All 19 physical/product SSC notes have 8/8 product families with runnable templates.** `SSC-20` remains excluded from the physical/product stream because it is a regional standards and authority overlay.

These runnable entries do not claim accepted project evidence, authority approval, executable real source-pack parsing, full standards compliance, generated benchmark readiness, or benchmark readiness.

| SSC | Products Covered | Remaining Products | Status | Evidence |
| --- | ---: | ---: | --- | --- |
| SSC-07 | 8/8 | 0 | Done | Existing `ground-structural-electrical-safety-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-01 | 8/8 | 0 | Done | Existing `road-low-point-resilience-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-14 | 8/8 | 0 | Done | Existing `pipe-transient-support-foundation-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-11 | 8/8 | 0 | Done | Existing `pump-transient-protection-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-03 | 8/8 | 0 | Done | Existing `detention-outlet-hgl-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-17 | 8/8 | 0 | Done | Existing `stormwater-pumping-outage-resilience-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-06 | 8/8 | 0 | Done | Existing `pump-station-duty-power-npsh-feeder-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-10 | 8/8 | 0 | Done | Existing `wastewater-energy-island-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-05 | 8/8 | 0 | Done | Existing `mechanical-load-feeder-voltage-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-02 | 8/8 | 0 | Done | Existing `level-crossing-warning-backup-power-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-19 | 8/8 | 0 | Done | Existing `fire-water-sprinkler-storage-package`, reused shared `bess-fire-containment-ventilation-feeder-package`, plus six new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-09 | 8/8 | 0 | Done | Existing `facade-wind-bracket-anchor-package`, reused shared `roof-drainage-gutter-downpipe-facade-interface-package`, plus six new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-04 | 8/8 | 0 | Done | Existing `coastal-flood-outfall-pump-elevation-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-08 | 8/8 | 0 | Done | Existing `station-population-egress-vertical-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-15 | 8/8 | 0 | Done | Existing `product-submittal-compliance-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-13 | 8/8 | 0 | Done | Existing `road-visual-operations-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-16 | 8/8 | 0 | Done | Existing `construction-stage-controls-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-12 | 8/8 | 0 | Done | Existing `acoustic-receiver-impact-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |
| SSC-18 | 8/8 | 0 | Done | Existing `control-loop-signal-package` plus seven new built-in synthetic templates; focused tests pass and each generated golden verifier scores `1.0`. |

## SSC-07 Product Expansion

The first note, `SSC-07 Ground investigation, groundwater, and soil/resistivity world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-07-LH-01` Soil And Groundwater Structural-Electrical Safety Package | `ground-structural-electrical-safety-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-07-LH-02` Retaining Wall Seepage, Uplift, And Foundation Package | `retaining-wall-seepage-uplift-foundation-package` | Generated golden verifier reward `1.0`. |
| `SSC-07-LH-03` Solar Array Wind Load, Ground Bearing, And Earthing Package | `solar-array-ground-bearing-earthing-package` | Generated golden verifier reward `1.0`. |
| `SSC-07-LH-04` Excavation/Dewatering And Temporary Power Safety Package | `excavation-dewatering-temporary-power-package` | Generated golden verifier reward `1.0`. |
| `SSC-07-LH-05` Liquefaction/Seismic Slope And Service Continuity Package | `seismic-slope-service-continuity-package` | Generated golden verifier reward `1.0`. |
| `SSC-07-LH-06` Ground Improvement Acceptance And Foundation Recheck Package | `ground-improvement-foundation-recheck-package` | Generated golden verifier reward `1.0`. |
| `SSC-07-LH-07` Buried Pipe, Thrust Block, And Soil Resistance Package | `buried-pipe-thrust-soil-resistance-package` | Generated golden verifier reward `1.0`. |
| `SSC-07-LH-08` Ground Investigation Review And Parameter Repair Package | `ground-investigation-parameter-repair-package` | Generated golden verifier reward `1.0`. |

## SSC-01 Product Expansion

The second note, `SSC-01 Road/corridor profile and traffic scene`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-01-LH-01` Road Low-Point Drainage And Field Equipment Resilience | `road-low-point-resilience-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-01-LH-02` Intersection Timing, Grade, And Sight-Distance Package | `intersection-timing-grade-sight-distance-package` | Generated golden verifier reward `1.0`. |
| `SSC-01-LH-03` Road Lighting, ITS, And Drainage Operations Scene | `road-lighting-its-drainage-operations-package` | Generated golden verifier reward `1.0`. |
| `SSC-01-LH-04` Emergency Detour And Roadside Device Continuity | `emergency-detour-roadside-device-continuity-package` | Generated golden verifier reward `1.0`. |
| `SSC-01-LH-05` Bus Priority, Signal Corridor, And Cabinet Load Package | `bus-priority-signal-cabinet-load-package` | Generated golden verifier reward `1.0`. |
| `SSC-01-LH-06` Culvert, Driveway Access, And Safety Continuity Package | `culvert-driveway-access-safety-continuity-package` | Generated golden verifier reward `1.0`. |
| `SSC-01-LH-07` Roadside Cabinet Flood, Heat, And Backup Energy Package | `roadside-cabinet-flood-heat-backup-energy-package` | Generated golden verifier reward `1.0`. |
| `SSC-01-LH-08` Multimodal Corridor Review Response Package | `multimodal-corridor-review-response-package` | Generated golden verifier reward `1.0`. |

## SSC-14 Product Expansion

The third note, `SSC-14 Structural load, support, foundation, and connection world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-14-LH-01` Pipe Transient Support And Foundation Package | `pipe-transient-support-foundation-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-14-LH-02` Facade Or Roof Bracket, Anchor, And Connection Package | `facade-roof-bracket-connection-package` | Generated golden verifier reward `1.0`. |
| `SSC-14-LH-03` Equipment Skid, Support, And Vibration Package | `equipment-skid-support-vibration-package` | Generated golden verifier reward `1.0`. |
| `SSC-14-LH-04` Retaining/Foundation Groundwater And Structural Stability Package | `retaining-foundation-groundwater-stability-package` | Generated golden verifier reward `1.0`. |
| `SSC-14-LH-05` Marine Fender, Mooring, And Berthing Structure Package | `marine-fender-mooring-berthing-structure-package` | Generated golden verifier reward `1.0`. |
| `SSC-14-LH-06` Wind Turbine Or Solar Foundation Package | `wind-solar-foundation-package` | Generated golden verifier reward `1.0`. |
| `SSC-14-LH-07` Construction Tolerance And Connection Repair Package | `construction-tolerance-connection-repair-package` | Generated golden verifier reward `1.0`. |
| `SSC-14-LH-08` Structural Review Packet And Authority Overlay | `structural-review-authority-overlay-package` | Generated golden verifier reward `1.0`. |

## SSC-11 Product Expansion

The fourth note, `SSC-11 Piping network, transient, thrust, and support world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-11-LH-01` Pump Transient, Thrust, Support, And Protection-Trip Package | `pump-transient-protection-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-11-LH-02` Fire-Main Hydraulic And Seismic Support Package | `fire-main-hydraulic-seismic-support-package` | Generated golden verifier reward `1.0`. |
| `SSC-11-LH-03` Process Piping Valve And Control Package | `process-piping-valve-control-package` | Generated golden verifier reward `1.0`. |
| `SSC-11-LH-04` Stormwater Outlet, Flap Gate, And Pipe HGL Package | `stormwater-outlet-flap-gate-hgl-package` | Generated golden verifier reward `1.0`. |
| `SSC-11-LH-05` Buried Pipeline Groundwater And Uplift Package | `buried-pipeline-groundwater-uplift-package` | Generated golden verifier reward `1.0`. |
| `SSC-11-LH-06` Pump Station Rising Main Energy And Surge Package | `pump-station-rising-main-energy-surge-package` | Generated golden verifier reward `1.0`. |
| `SSC-11-LH-07` Pipe Material/Product And Velocity Compliance Package | `pipe-material-velocity-compliance-package` | Generated golden verifier reward `1.0`. |
| `SSC-11-LH-08` Piping Network Repair And Negative-Case Portfolio | `piping-network-repair-negative-case-package` | Generated golden verifier reward `1.0`. |

## SSC-03 Product Expansion

The fifth note, `SSC-03 Stormwater catchment, drainage, and hydraulic grade world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-03-LH-01` Detention And Outlet Design-Check Package | `detention-outlet-hgl-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-03-LH-02` Drainage Long Section, HGL, And Road Low-Point Package | `drainage-long-section-hgl-road-low-point-package` | Generated golden verifier reward `1.0`. |
| `SSC-03-LH-03` Stormwater Pump Station Control And Backup-Energy Package | `stormwater-pump-station-control-backup-energy-package` | Generated golden verifier reward `1.0`. |
| `SSC-03-LH-04` Roof Drainage, Gutter/Downpipe, And Facade Interface Package | `roof-drainage-gutter-downpipe-facade-interface-package` | Generated golden verifier reward `1.0`. |
| `SSC-03-LH-05` Outfall Tailwater, Flap Gate, And Coastal Boundary Package | `outfall-tailwater-flap-gate-coastal-boundary-package` | Generated golden verifier reward `1.0`. |
| `SSC-03-LH-06` Water Quality, Pollutant Load, And Construction Sediment Package | `water-quality-pollutant-load-construction-sediment-package` | Generated golden verifier reward `1.0`. |
| `SSC-03-LH-07` Sewer/Storm Pipe Gradient And Capacity Repair Package | `sewer-storm-pipe-gradient-capacity-repair-package` | Generated golden verifier reward `1.0`. |
| `SSC-03-LH-08` SWMM/HEC-Style Report Output And Source-Policy Package | `swmm-hec-report-source-policy-package` | Generated golden verifier reward `1.0`. |

## SSC-17 Product Expansion

The sixth note, `SSC-17 Energy resource, storage, resilience, and operating time-series world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-17-LH-01` DER Resilience And Feeder Interconnection | `der-resilience-feeder-interconnection-package` | Generated golden verifier reward `1.0`. |
| `SSC-17-LH-02` Wastewater Energy Island | `wastewater-energy-island-resilience-package` | Generated golden verifier reward `1.0`. |
| `SSC-17-LH-03` Stormwater Controls And Pumping Outage Resilience | `stormwater-pumping-outage-resilience-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-17-LH-04` BESS Fire, Containment, Ventilation, And Feeder | `bess-fire-containment-ventilation-feeder-package` | Generated golden verifier reward `1.0`. |
| `SSC-17-LH-05` Road And ITS Field Equipment Energy Resilience | `road-its-field-equipment-energy-resilience-package` | Generated golden verifier reward `1.0`. |
| `SSC-17-LH-06` Station Emergency Operations Energy Package | `station-emergency-operations-energy-package` | Generated golden verifier reward `1.0`. |
| `SSC-17-LH-07` Rail Corridor Weather, Electrical Capacity, And Backup Operations | `rail-weather-electrical-backup-operations-package` | Generated golden verifier reward `1.0`. |
| `SSC-17-LH-08` Coastal Or Marine Flood Energy Resilience | `coastal-marine-flood-energy-resilience-package` | Generated golden verifier reward `1.0`. |

## SSC-06 Product Expansion

The seventh note, `SSC-06 Equipment layout, motor schedule, and duty-point world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-06-LH-01` Pump Station Duty, Power, NPSH, And Feeder Package | `pump-station-duty-power-npsh-feeder-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-06-LH-02` Blower Process, Energy, And Acoustic Impact Package | `blower-process-energy-acoustic-package` | Generated golden verifier reward `1.0`. |
| `SSC-06-LH-03` Compressor Or Pneumatic System Package | `compressor-pneumatic-system-package` | Generated golden verifier reward `1.0`. |
| `SSC-06-LH-04` Equipment Support, Foundation, And Vibration Package | `equipment-support-foundation-vibration-package` | Generated golden verifier reward `1.0`. |
| `SSC-06-LH-05` Pump Affinity, Retrofit, And Energy-Performance Package | `pump-affinity-retrofit-energy-package` | Generated golden verifier reward `1.0`. |
| `SSC-06-LH-06` Heat Exchanger Or Thermal Plant Equipment Package | `heat-exchanger-thermal-plant-equipment-package` | Generated golden verifier reward `1.0`. |
| `SSC-06-LH-07` Marine Or Coastal Pumping Equipment Package | `marine-coastal-pumping-equipment-package` | Generated golden verifier reward `1.0`. |
| `SSC-06-LH-08` Equipment Datasheet And Commissioning Review Package | `equipment-datasheet-commissioning-review-package` | Generated golden verifier reward `1.0`. |

## SSC-10 Product Expansion

The eighth note, `SSC-10 Process wastewater, treatment, and plant energy world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-10-LH-01` Wastewater Energy Island | `wastewater-energy-island-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-10-LH-02` Aeration Blower Process, Power, And Acoustic Package | `aeration-blower-process-power-acoustic-package` | Generated golden verifier reward `1.0`. |
| `SSC-10-LH-03` Chemical Dosing, Storage, And Containment Package | `chemical-dosing-storage-containment-package` | Generated golden verifier reward `1.0`. |
| `SSC-10-LH-04` Instrumented Process Control And Valve Package | `instrumented-process-control-valve-package` | Generated golden verifier reward `1.0`. |
| `SSC-10-LH-05` Clarifier Loading, Sludge, And Hydraulic Constraint Package | `clarifier-sludge-hydraulic-constraint-package` | Generated golden verifier reward `1.0`. |
| `SSC-10-LH-06` Wet-Weather Process And Bypass Resilience Package | `wet-weather-process-bypass-resilience-package` | Generated golden verifier reward `1.0`. |
| `SSC-10-LH-07` Biogas, Sludge, And Generator Dispatch Package | `biogas-sludge-generator-dispatch-package` | Generated golden verifier reward `1.0`. |
| `SSC-10-LH-08` Treatment Review Response And Permit-Basis Package | `treatment-review-permit-basis-package` | Generated golden verifier reward `1.0`. |

## SSC-05 Product Expansion

The ninth note, `SSC-05 Electrical SLD, feeder, load, and protection world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-05-LH-01` Mechanical-Load To Feeder And Voltage Package | `mechanical-load-feeder-voltage-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-05-LH-02` PV/BESS Interconnection And Export-Control Package | `pv-bess-interconnection-export-control-package` | Generated golden verifier reward `1.0`. |
| `SSC-05-LH-03` Switchboard Fault, Arc-Flash, And Earthing Package | `switchboard-fault-arcflash-earthing-package` | Generated golden verifier reward `1.0`. |
| `SSC-05-LH-04` Fire/Life-Safety And Communications Load Package | `fire-life-safety-communications-load-package` | Generated golden verifier reward `1.0`. |
| `SSC-05-LH-05` Pump Station MCC, Cable, And Protection Package | `pump-station-mcc-cable-protection-package` | Generated golden verifier reward `1.0`. |
| `SSC-05-LH-06` PoE, Fibre, And Field Cabinet Power Package | `poe-fibre-field-cabinet-power-package` | Generated golden verifier reward `1.0`. |
| `SSC-05-LH-07` Regional Load-Flow And Voltage-Regulation Review Package | `regional-load-flow-voltage-regulation-package` | Generated golden verifier reward `1.0`. |
| `SSC-05-LH-08` Electrical Source-Policy And Product Datasheet Package | `electrical-source-policy-product-datasheet-package` | Generated golden verifier reward `1.0`. |

## SSC-02 Product Expansion

The tenth note, `SSC-02 Rail corridor profile, signalling, and OLE`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-02-LH-01` Rail Braking, Sighting, And Warning-Time Corridor Package | `rail-braking-sighting-warning-time-corridor-package` | Generated golden verifier reward `1.0`. |
| `SSC-02-LH-02` OLE Sag, Thermal Stress, And Signal Clearance Package | `ole-sag-thermal-stress-signal-clearance-package` | Generated golden verifier reward `1.0`. |
| `SSC-02-LH-03` Level Crossing Backup-Power And Degraded-Mode Operations | `level-crossing-warning-backup-power-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-02-LH-04` Rail Drainage, Flood Clearance, And Speed Restriction Package | `rail-drainage-flood-clearance-speed-restriction-package` | Generated golden verifier reward `1.0`. |
| `SSC-02-LH-05` Route Profile, Cant, And Rolling-Stock Braking Package | `route-profile-cant-rolling-stock-braking-package` | Generated golden verifier reward `1.0`. |
| `SSC-02-LH-06` Signal Overlap, Approach Speed, And Sighting Photo Package | `signal-overlap-approach-speed-sighting-photo-package` | Generated golden verifier reward `1.0`. |
| `SSC-02-LH-07` Wayside Cabinet Load, Communications, And Backup Supply Package | `wayside-cabinet-load-communications-backup-supply-package` | Generated golden verifier reward `1.0`. |
| `SSC-02-LH-08` Rail Standards Conflict And Operator Review Package | `rail-standards-conflict-operator-review-package` | Generated golden verifier reward `1.0`. |

## SSC-19 Product Expansion

The eleventh note, `SSC-19 Fire, hazard, suppression, and tenability world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-19-LH-01` Fire-Water, Sprinkler Demand, And Storage Hazard Package | `fire-water-sprinkler-storage-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-19-LH-02` BESS Hazard, Containment, Ventilation, And Feeder Package | `bess-fire-containment-ventilation-feeder-package` | Reused shared built-in template; generated golden verifier reward `1.0`. |
| `SSC-19-LH-03` Structural Fire And Tenability Package | `structural-fire-tenability-package` | Generated golden verifier reward `1.0`. |
| `SSC-19-LH-04` Alarm, Smoke Control, And Emergency Power Package | `alarm-smoke-control-emergency-power-package` | Generated golden verifier reward `1.0`. |
| `SSC-19-LH-05` Warehouse Hazard, Storage Arrangement, And FM/AHJ Review Package | `warehouse-hazard-storage-fm-ahj-review-package` | Generated golden verifier reward `1.0`. |
| `SSC-19-LH-06` Fire Pump Fuel, Power, And Control Resilience Package | `fire-pump-power-control-resilience-package` | Generated golden verifier reward `1.0`. |
| `SSC-19-LH-07` Bund/Containment, Fire Water, And Environmental Isolation Package | `bund-containment-firewater-environmental-isolation-package` | Generated golden verifier reward `1.0`. |
| `SSC-19-LH-08` Fire Review Response And Evidence Boundary Package | `fire-review-response-evidence-boundary-package` | Generated golden verifier reward `1.0`. |

## SSC-09 Product Expansion

The twelfth note, `SSC-09 Roof/facade/envelope wind, drainage, and fixing world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-09-LH-01` Facade Wind, Bracket, Anchor, And Tolerance Package | `facade-wind-bracket-anchor-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-09-LH-02` Roof Drainage, PV Layout, And Wind Uplift Package | `roof-drainage-pv-uplift-package` | Generated golden verifier reward `1.0`. |
| `SSC-09-LH-03` Envelope Access, Maintenance, And Safety Package | `envelope-access-maintenance-safety-package` | Generated golden verifier reward `1.0`. |
| `SSC-09-LH-04` Canopy, Signage, Lighting, And Envelope Fixing Package | `canopy-signage-lighting-fixing-package` | Generated golden verifier reward `1.0`. |
| `SSC-09-LH-05` Rainscreen Drainage, Cavity, And Fire/Material Review Package | `rainscreen-drainage-cavity-fire-material-review-package` | Generated golden verifier reward `1.0`. |
| `SSC-09-LH-06` Facade Zone Difference And Re-Entrant Geometry Package | `facade-zone-reentrant-geometry-package` | Generated golden verifier reward `1.0`. |
| `SSC-09-LH-07` Roof/Fall/Drainage Conflict And Repair Package | `roof-drainage-gutter-downpipe-facade-interface-package` | Reused shared built-in template; generated golden verifier reward `1.0`. |
| `SSC-09-LH-08` Facade Submittal Review And Source-Policy Package | `facade-submittal-source-policy-package` | Generated golden verifier reward `1.0`. |

## SSC-04 Product Expansion

The thirteenth note, `SSC-04 Coastal, flood, wave, and marine boundary world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-04-LH-01` Coastal Flood, Outfall, Pump, And Electrical Elevation Package | `coastal-flood-outfall-pump-elevation-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-04-LH-02` Wave Runup, Freeboard, And Asset Protection Package | `wave-runup-freeboard-asset-protection-package` | Generated golden verifier reward `1.0`. |
| `SSC-04-LH-03` Marine Berthing, Fender, And Storm Operations Package | `marine-berthing-fender-storm-operations-package` | Generated golden verifier reward `1.0`. |
| `SSC-04-LH-04` Flap Gate, Tide, And Drainage Resilience Package | `flap-gate-tide-drainage-resilience-package` | Generated golden verifier reward `1.0`. |
| `SSC-04-LH-05` Coastal Erosion, Longshore Transport, And Temporary Works Package | `coastal-erosion-longshore-temporary-works-package` | Generated golden verifier reward `1.0`. |
| `SSC-04-LH-06` Sea-Level-Rise Scenario And Asset-Level Review Package | `sea-level-rise-asset-review-package` | Generated golden verifier reward `1.0`. |
| `SSC-04-LH-07` Coastal Pump-Out And Generator Autonomy Package | `coastal-pumpout-generator-autonomy-package` | Generated golden verifier reward `1.0`. |
| `SSC-04-LH-08` Marine Asset Source-Policy And Review Packet | `marine-asset-source-policy-review-package` | Generated golden verifier reward `1.0`. |

## SSC-08 Product Expansion

The fourteenth note, `SSC-08 Building occupancy, room, egress, and vertical movement world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-08-LH-01` Station Population, Vertical Movement, Egress, Alarm, And Ventilation Package | `station-population-egress-vertical-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-08-LH-02` Room Occupancy, Lighting Energy, And Access-Control Package | `room-occupancy-lighting-access-control-package` | Generated golden verifier reward `1.0`. |
| `SSC-08-LH-03` Emergency Power For Life-Safety And Vertical Movement | `life-safety-vertical-movement-emergency-power-package` | Generated golden verifier reward `1.0`. |
| `SSC-08-LH-04` Crowd, CCTV, And Communications Operations Package | `crowd-cctv-communications-operations-package` | Generated golden verifier reward `1.0`. |
| `SSC-08-LH-05` Smoke Control, Visibility, And Egress Interaction Package | `smoke-control-visibility-egress-interaction-package` | Generated golden verifier reward `1.0`. |
| `SSC-08-LH-06` Lift Shaft, Car Dimension, And Accessibility Service Package | `lift-shaft-car-accessibility-service-package` | Generated golden verifier reward `1.0`. |
| `SSC-08-LH-07` Pedestrian Clearance, Building Forecourt, And Signal Interface | `pedestrian-clearance-forecourt-signal-interface-package` | Generated golden verifier reward `1.0`. |
| `SSC-08-LH-08` Building Operations Review And Scenario Repair Package | `building-operations-scenario-repair-package` | Generated golden verifier reward `1.0`. |

## SSC-15 Product Expansion

The fifteenth note, `SSC-15 Material/product compliance and certificate world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-15-LH-01` Steel Certificate To Structural/Fire/Carbon Package | `steel-certificate-structural-fire-carbon-package` | Generated golden verifier reward `1.0`. |
| `SSC-15-LH-02` Cable/Component Datasheet To Ampacity And Voltage Package | `cable-component-datasheet-ampacity-voltage-package` | Generated golden verifier reward `1.0`. |
| `SSC-15-LH-03` Concrete Or Mix Compliance And Drainage/Retaining Use Package | `concrete-mix-drainage-retaining-compliance-package` | Generated golden verifier reward `1.0`. |
| `SSC-15-LH-04` Product Submittal Review Packet Overlay | `product-submittal-compliance-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-15-LH-05` Pipe Product Velocity, Slope, And Certificate Package | `pipe-product-velocity-slope-certificate-package` | Generated golden verifier reward `1.0`. |
| `SSC-15-LH-06` Facade/Fixing Product Certificate And Capacity Package | `facade-fixing-certificate-capacity-package` | Generated golden verifier reward `1.0`. |
| `SSC-15-LH-07` Code Compliance Note For Occupancy/Fire/Product Class | `occupancy-fire-product-class-compliance-package` | Generated golden verifier reward `1.0`. |
| `SSC-15-LH-08` Certificate Conflict And Repair Portfolio | `certificate-conflict-repair-portfolio-package` | Generated golden verifier reward `1.0`. |

## SSC-13 Product Expansion

The sixteenth note, `SSC-13 Lighting, visual performance, ITS, CCTV, and communications scene`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-13-LH-01` Road Visual Operations, ITS, CCTV, Lighting, And Comms Power Package | `road-visual-operations-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-13-LH-02` Station Or Building Security And Lighting Package | `station-building-security-lighting-package` | Generated golden verifier reward `1.0`. |
| `SSC-13-LH-03` Sports Or Field Lighting Power And Uniformity Package | `sports-field-lighting-power-uniformity-package` | Generated golden verifier reward `1.0`. |
| `SSC-13-LH-04` Remote ITS Backup Communications Package | `remote-its-backup-communications-package` | Generated golden verifier reward `1.0`. |
| `SSC-13-LH-05` VMS Message Library, Legibility, And Power Package | `vms-message-legibility-power-package` | Generated golden verifier reward `1.0`. |
| `SSC-13-LH-06` CCTV Coverage, Pixel Density, And Storage Package | `cctv-coverage-pixel-storage-package` | Generated golden verifier reward `1.0`. |
| `SSC-13-LH-07` Lighting Energy And Emergency Mode Package | `lighting-energy-emergency-mode-package` | Generated golden verifier reward `1.0`. |
| `SSC-13-LH-08` Visual Systems Review And Repair Package | `visual-systems-review-repair-package` | Generated golden verifier reward `1.0`. |

## SSC-16 Product Expansion

The seventeenth note, `SSC-16 Construction, temporary works, environmental controls, and staging world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-16-LH-01` Construction Environmental Controls, Temporary Traffic, And Monitoring Power Package | `construction-stage-controls-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-16-LH-02` Temporary Works Wind And Structural Staging Package | `temporary-works-wind-structural-staging-package` | Generated golden verifier reward `1.0`. |
| `SSC-16-LH-03` Dewatering, Settlement, And Temporary Power Package | `dewatering-settlement-temporary-power-package` | Generated golden verifier reward `1.0`. |
| `SSC-16-LH-04` Staged Road/ITS Relocation Package | `staged-road-its-relocation-package` | Generated golden verifier reward `1.0`. |
| `SSC-16-LH-05` Sediment Basin And Storm Event Readiness Package | `sediment-basin-storm-readiness-package` | Generated golden verifier reward `1.0`. |
| `SSC-16-LH-06` Temporary Fuel/Chemical Bund And Fire Interface Package | `temporary-fuel-chemical-bund-fire-interface-package` | Generated golden verifier reward `1.0`. |
| `SSC-16-LH-07` Construction Monitoring Network And Data Continuity Package | `construction-monitoring-network-continuity-package` | Generated golden verifier reward `1.0`. |
| `SSC-16-LH-08` Staging Review Response And Negative-Case Package | `staging-review-response-negative-case-package` | Generated golden verifier reward `1.0`. |

## SSC-12 Product Expansion

The eighteenth note, `SSC-12 Acoustic, vibration, and receiver-impact world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-12-LH-01` Blower Or Pump Duty To Acoustic Impact Package | `acoustic-receiver-impact-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-12-LH-02` Vibration Isolation And Support Package | `vibration-isolation-support-package` | Generated golden verifier reward `1.0`. |
| `SSC-12-LH-03` Room Acoustic And HVAC Operations Package | `room-acoustic-hvac-operations-package` | Generated golden verifier reward `1.0`. |
| `SSC-12-LH-04` Construction Noise And Vibration Monitoring Package | `construction-noise-vibration-monitoring-package` | Generated golden verifier reward `1.0`. |
| `SSC-12-LH-05` Rail Or Road Receiver Impact Package | `rail-road-receiver-impact-package` | Generated golden verifier reward `1.0`. |
| `SSC-12-LH-06` Fire Alarm Audibility And Occupancy Package | `fire-alarm-audibility-occupancy-package` | Generated golden verifier reward `1.0`. |
| `SSC-12-LH-07` Equipment Enclosure, Ventilation, And Noise Package | `equipment-enclosure-ventilation-noise-package` | Generated golden verifier reward `1.0`. |
| `SSC-12-LH-08` Acoustic Review Repair And Source-Policy Package | `acoustic-review-repair-source-policy-package` | Generated golden verifier reward `1.0`. |

## SSC-18 Product Expansion

The nineteenth physical/product note, `SSC-18 Instrumentation, controls, valve, and process signal world`, now has runnable synthetic examples for all eight products:

| Product | Runnable Template | Validation |
| --- | --- | --- |
| `SSC-18-LH-01` Valve Cv, Process Value, And Signal Scaling Package | `control-loop-signal-package` | Existing template; two-model `tool_loop` reward `1.0`. |
| `SSC-18-LH-02` Stormwater Or Treatment Telemetry Control Package | `stormwater-treatment-telemetry-control-package` | Generated golden verifier reward `1.0`. |
| `SSC-18-LH-03` Protection And Control Setting Bridge To SLD | `protection-control-sld-bridge-package` | Generated golden verifier reward `1.0`. |
| `SSC-18-LH-04` Commissioning And Calibration Review Packet | `commissioning-calibration-review-package` | Generated golden verifier reward `1.0`. |
| `SSC-18-LH-05` Chemical Dosing Flowmeter And Control Package | `chemical-dosing-flowmeter-control-package` | Generated golden verifier reward `1.0`. |
| `SSC-18-LH-06` Fire Pump Pressure Signal And Alarm Package | `fire-pump-pressure-signal-alarm-package` | Generated golden verifier reward `1.0`. |
| `SSC-18-LH-07` Valve Failure And Safe-State Repair Package | `valve-failure-safe-state-repair-package` | Generated golden verifier reward `1.0`. |
| `SSC-18-LH-08` Instrumentation Source-Policy And Thin-Substrate Extension Package | `instrumentation-source-policy-extension-package` | Generated golden verifier reward `1.0`. |

No physical/product SSC notes remain in this all-product expansion stream; `SSC-20` remains excluded as a regional standards and authority overlay.
