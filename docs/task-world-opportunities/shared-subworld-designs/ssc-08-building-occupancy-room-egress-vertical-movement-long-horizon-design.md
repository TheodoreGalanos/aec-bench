# SSC-08 Building occupancy, room, egress, and vertical movement world Long-Horizon Design

This document treats the building or station area as one source-controlled package: room use, population, egress route, lift or escalator group, fire zones, ventilation, and alarm assumptions have to line up. A useful long-horizon task keeps that building basis consistent while moving between occupant load, vertical movement, egress, alarm, ventilation, and emergency operation checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Building source state | floor/room plan, occupancy/population schedule, egress route, lift/escalator group, fire alarm zones |
| Memberships | 20 task-card memberships |
| Primary cards | 7 |
| Disciplines | electrical, mechanical |
| Score | 25/30 |
| Candidate product | Station population, vertical movement, egress, alarm, and ventilation package |
| Main risk | Can become too broad unless scoped to one floor/zone and scenario. |

The current card anchors cover occupancy, egress, lift, escalator, fire-alarm, ventilation, room, and access-control checks:

| Card | Plain-language role |
| --- | --- |
| `access-controller-sizing` | Size access controllers, power supplies, and backup battery capacity. |
| `all-red-interval-calculation` | Traffic signal all-red clearance interval. |
| `car-dimensions-check` | Calculates lift car dimension margins. |
| `cctv-storage-calculation` | CCTV video storage sizing from bitrate and retention. |
| `escalator-capacity` | Escalator theoretical and practical passenger capacity. |
| `handling-capacity` | Five-minute lift handling capacity percentage. |
| `interval-calculation` | Average lift interval from round-trip time and lift count. |
| `lux-level-calculation` | Calculates average room illuminance using the lumen method. |
| `ppm-calculation` | CCTV pixels-per-metre calculation from camera geometry. |
| `shaft-dimensions` | Calculates reduced lift shaft dimensions. |

## Building Occupancy Data Model

Treat each task as a check against the same building occupancy and movement package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-08`, the building occupancy and movement package source state is:

```text
S_ssc_08 = {
  floor_zone_model,
  population_basis,
  egress_routes,
  vertical_transport,
  life_safety_loads,
  normal_operations,
  emergency_mode,
  authority_partition,
}
```

The product combinations below share the same building occupancy and movement package data. A change to room use, population, egress route, lift or escalator group, fire zone, ventilation case, or alarm zone must carry through each check.

```text
W_ssc08_lh_01 x_S W_ssc08_lh_02
W_ssc08_lh_02 x_S W_ssc08_lh_03
W_ssc08_lh_03 x_S W_ssc08_lh_04
W_ssc08_lh_04 x_S W_ssc08_lh_05
W_ssc08_lh_05 x_S W_ssc08_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_08` | The building occupancy and movement package source state that all combined checks must agree on. |
| `W_ssc08_lh_01` | The first SSC-08 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same building occupancy and movement package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Building Source Manifest

Any `SSC-08` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `floor_zone_model` | Floor, room, zone, shaft, route, and fire compartment identities. | architectural plan |
| `population_basis` | Occupancy counts, peak period, special users, and scenario class. | occupancy schedule |
| `egress_routes` | Doors, corridors, stairs, exits, widths, and travel routes. | life-safety plan |
| `vertical_transport` | Lift/escalator group, car/shaft dimensions, handling capacity, interval. | traffic study |
| `life_safety_loads` | NAC, smoke control, emergency lighting, access, and ventilation loads. | life-safety load schedule |
| `normal_operations` | Normal circulation, lighting, access control, CCTV, and HVAC state. | operations schedule |
| `emergency_mode` | Fire, outage, evacuation, accessibility, or degraded-service scenario. | fire/emergency plan |
| `authority_partition` | Building code, fire, vertical transport, mechanical, electrical, and owner criteria split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-08-LH-01: Station Population, Vertical Movement, Egress, Alarm, And Ventilation Package

This is a building occupancy and egress work package for station population, vertical movement, egress, alarm, and ventilation. It starts with the floor/station plan, population schedule, and lift/escalator data.

The engineer checks lift/escalator handling, egress width and travel scenario, and alarm/ventilation/electrical load. The output is the life-safety operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
population and operating mode
  -> lift/escalator handling
  -> egress width and travel scenario
  -> alarm/ventilation/electrical load
  -> life-safety operations memo
```

Task-card anchors:

- `occupant-load`
- `egress-width`
- `escalator-capacity`
- `handling-capacity`
- `nac-load-calculation`

Source pack:

- floor/station plan;
- population schedule;
- lift/escalator data;
- fire alarm and ventilation load schedule;
- egress/life-safety criteria.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change floor/station plan while keeping the downstream lift/escalator handling fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make floor/station plan disagree with population schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in lift/escalator data only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on population and operating mode. The response should show lift/escalator handling and egress width and travel scenario, then record life-safety operations memo using the same source values throughout.

### SSC-08-LH-02: Room Occupancy, Lighting Energy, And Access-Control Package

This is a building occupancy and egress work package for room occupancy, lighting energy, and access-control. It starts with the room plan, occupancy schedule, and lighting layout.

The engineer checks lighting/illuminance target, access-control device schedule, and LENI or energy check. The output is the room operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
room plan and occupancy
  -> lighting/illuminance target
  -> access-control device schedule
  -> LENI or energy check
  -> room operations memo
```

Task-card anchors:

- `occupant-load`
- `lux-level-calculation`
- `interior-uniformity`
- `access-controller-sizing`
- `leni-calculation`

Source pack:

- room plan;
- occupancy schedule;
- lighting layout;
- access-control device list;
- energy or operating profile.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change room plan while keeping the downstream lighting/illuminance target fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make room plan disagree with occupancy schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in lighting layout only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on room plan and occupancy. The response should show lighting/illuminance target and access-control device schedule, then record room operations memo using the same source values throughout.

### SSC-08-LH-03: Emergency Power For Life-Safety And Vertical Movement

This is a building occupancy and egress work package for emergency power for life-safety and vertical movement. It starts with the emergency operations plan, lift/escalator schedule, and fire alarm load schedule.

The engineer checks critical lift/escalator/alarm loads, battery/generator bridge, and load-shedding decision. The output is the emergency power memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
emergency scenario
  -> critical lift/escalator/alarm loads
  -> battery/generator bridge
  -> load-shedding decision
  -> emergency power memo
```

Task-card anchors:

- `battery-sizing`
- `bess-sizing-basic`
- `nac-load-calculation`
- `escalator-capacity`
- `voltage-drop`

Source pack:

- emergency operations plan;
- lift/escalator schedule;
- fire alarm load schedule;
- battery/generator data sheet;
- load-shed sequence.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change emergency operations plan while keeping the downstream critical lift/escalator/alarm loads fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make emergency operations plan disagree with lift/escalator schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in fire alarm load schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on emergency scenario. The response should show critical lift/escalator/alarm loads and battery/generator bridge, then record emergency power memo using the same source values throughout.

### SSC-08-LH-04: Crowd, CCTV, And Communications Operations Package

This is a building occupancy and egress work package for crowd, CCTV, and communications operations. It starts with the population/queue schedule, camera layout, and network topology.

The engineer checks CCTV coverage/storage, communications bandwidth and PoE, and access-control state. The output is the security operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
population and queue scenario
  -> CCTV coverage/storage
  -> communications bandwidth and PoE
  -> access-control state
  -> security operations memo
```

Task-card anchors:

- `cctv-storage-calculation`
- `ppm-calculation`
- `bandwidth-calculation`
- `poe-power-budget`
- `access-controller-sizing`

Source pack:

- population/queue schedule;
- camera layout;
- network topology;
- PoE switch schedule;
- access-control list.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change population/queue schedule while keeping the downstream CCTV coverage/storage fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make population/queue schedule disagree with camera layout about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in network topology only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on population and queue scenario. The response should show CCTV coverage/storage and communications bandwidth and PoE, then record security operations memo using the same source values throughout.

### SSC-08-LH-05: Smoke Control, Visibility, And Egress Interaction Package

This is a building occupancy and egress work package for smoke control, visibility, and egress interaction. It starts with the fire strategy, population schedule, and ventilation schedule.

The engineer checks smoke/visibility or air-change criterion, egress capacity, and alarm/ventilation load. The output is the tenability memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
fire mode and population
  -> smoke/visibility or air-change criterion
  -> egress capacity
  -> alarm/ventilation load
  -> tenability memo
```

Task-card anchors:

- `visibility-criterion`
- `air-changes`
- `egress-width`
- `nac-load-calculation`
- `battery-sizing`

Source pack:

- fire strategy;
- population schedule;
- ventilation schedule;
- egress plan;
- visibility criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change fire strategy while keeping the downstream smoke/visibility or air-change criterion fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make fire strategy disagree with population schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in ventilation schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on fire mode and population. The response should show smoke/visibility or air-change criterion and egress capacity, then record tenability memo using the same source values throughout.

### SSC-08-LH-06: Lift Shaft, Car Dimension, And Accessibility Service Package

This is a building occupancy and egress work package for lift shaft, car dimension, and accessibility service. It starts with the floor/shaft plan, car and shaft data, and population/accessibility schedule.

The engineer checks population/accessibility demand, shaft/car dimensional check, and emergency power or fire-service branch. The output is the vertical transport memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
building section and car geometry
  -> population/accessibility demand
  -> shaft/car dimensional check
  -> emergency power or fire-service branch
  -> vertical transport memo
```

Task-card anchors:

- `car-dimensions-check`
- `shaft-dimensions`
- `handling-capacity`
- `battery-sizing`
- `voltage-drop`

Source pack:

- floor/shaft plan;
- car and shaft data;
- population/accessibility schedule;
- emergency lift rule;
- power schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change floor/shaft plan while keeping the downstream population/accessibility demand fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make floor/shaft plan disagree with car and shaft data about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in population/accessibility schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on building section and car geometry. The response should show population/accessibility demand and shaft/car dimensional check, then record vertical transport memo using the same source values throughout.

### SSC-08-LH-07: Pedestrian Clearance, Building Forecourt, And Signal Interface

This is a building occupancy and egress work package for pedestrian clearance, building forecourt, and signal interface. It starts with the station/forecourt plan, pedestrian demand schedule, and signal timing sheet.

The engineer checks road or crossing timing, egress discharge route, and visibility/lighting state. The output is the interface memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
entry/forecourt population
  -> road or crossing timing
  -> egress discharge route
  -> visibility/lighting state
  -> interface memo
```

Task-card anchors:

- `pedestrian-clearance-time`
- `all-red-interval-calculation`
- `handling-capacity`
- `lux-level-calculation`
- `occupant-load`

Source pack:

- station/forecourt plan;
- pedestrian demand schedule;
- signal timing sheet;
- lighting layout;
- road authority criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change station/forecourt plan while keeping the downstream road or crossing timing fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make station/forecourt plan disagree with pedestrian demand schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in signal timing sheet only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on entry/forecourt population. The response should show road or crossing timing and egress discharge route, then record interface memo using the same source values throughout.

### SSC-08-LH-08: Building Operations Review And Scenario Repair Package

This is a building occupancy and egress work package for building operations review and scenario repair. It starts with the room/floor plan, occupancy source table, and system schedules.

The engineer checks review comment or changed occupancy, affected system checks, and repair ledger. The output is the operations response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
source pack and scenario
  -> review comment or changed occupancy
  -> affected system checks
  -> repair ledger
  -> operations response
```

Task-card anchors:

- `occupant-load`
- `egress-width`
- `air-changes`
- `access-controller-sizing`
- `battery-sizing`

Source pack:

- room/floor plan;
- occupancy source table;
- system schedules;
- criteria matrix;
- comment register.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change room/floor plan while keeping the downstream review comment or changed occupancy fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make room/floor plan disagree with occupancy source table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in system schedules only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on design files and scenario. The response should show review comment or changed occupancy and affected system checks, then record operations response using the same source values throughout.

## How The Variants Come Together

All `SSC-08` variants should use the same building occupancy and movement package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the building occupancy and movement package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-08-LH-01` | Station Population, Vertical Movement, Egress, Alarm, And Ventilation Package | `floor_zone_model` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-08-LH-02` | Room Occupancy, Lighting Energy, And Access-Control Package | `population_basis` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-08-LH-03` | Emergency Power For Life-Safety And Vertical Movement | `egress_routes` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-08-LH-04` | Crowd, CCTV, And Communications Operations Package | `vertical_transport` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-08-LH-05` | Smoke Control, Visibility, And Egress Interaction Package | `life_safety_loads` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-08-LH-06` | Lift Shaft, Car Dimension, And Accessibility Service Package | `normal_operations` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-08-LH-07` | Pedestrian Clearance, Building Forecourt, And Signal Interface | `emergency_mode` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-08-LH-08` | Building Operations Review And Scenario Repair Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The building package should keep the same room use, population schedule, egress routes, lift or escalator group, fire zones, ventilation, and alarm assumptions across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when the package is treated as an occupancy-and-operations study over one floor, zone, station, or public venue. Real workflows keep room use, population basis, floor/zone geometry, egress routes, lift/escalator service assumptions, alarm mode, smoke-control or ventilation case, and emergency-power state synchronized.
- The long-horizon behaviour appears when normal movement and emergency operation diverge: a station peak-flow case, an assisted evacuation case, a smoke-control case, or a lift/escalator outage changes the population or route ledger.
- The product list is strongest if it does not try to model an entire building at once. It should force one named scenario and preserve the same occupant register through code checks, simulation, vertical-transport planning, and review comments.

Typical practitioner steps:

1. Register floor/zone geometry, room uses, occupant loads or schedules, accessible routes, vertical-transport assets, fire/smoke zones, alarm modes, and authority basis.
2. Build normal and emergency movement scenarios, including route availability, door/stair/escalator/lift constraints, assisted evacuation assumptions, and emergency-power dependencies.
3. Run egress, queueing, vertical movement, smoke-control/visibility, and life-safety interaction checks against the same scenario and population basis.
4. Issue a memo that ties geometry, population, route choices, operating mode, model outputs, code basis, and unresolved review assumptions together.

Software stack notes:

- [Pathfinder](https://www.thunderheadeng.com/pathfinder/) is a realistic egress and crowd-movement simulation anchor for evacuation, assisted evacuation, door availability, signage, environmental cues, and scenario comparison.
- [Oasys MassMotion](https://www.oasys-software.com/products/pedestrian-simulation-software/massmotion/) is a realistic pedestrian and crowd-modelling anchor for BIM import, population schedules, queueing, congestion, wait times, trip times, and transport/public-venue operations.
- [NFPA 101](https://www.nfpa.org/codes-and-standards/nfpa-101-standard-development/101) and [ICC IBC](https://codes.iccsafe.org/content/IBC2024P1) are realistic code routes for life-safety and egress criteria, but grading needs accessible clauses, authority criteria, or task-owned excerpts.
- [FDS and Smokeview](https://pages.nist.gov/fds-smv/) remain relevant when visibility, smoke, detector response, or tenability is coupled to egress rather than handled as a separate fire-only model.

Design implications:

- Add `floor_zone_model`, `population_basis`, `egress_route_register`, `vertical_transport_register`, `operating_mode_ledger`, and `life_safety_loads` fields before hardening `SSC-08-LH-01`.
- Require scenario IDs, route IDs, room/zone IDs, lift/escalator IDs, alarm mode, and emergency-power state to survive across movement, egress, fire/smoke, and review outputs.
- Negative cases should include population drift between code and simulation checks, swapped normal/emergency modes, an inaccessible route treated as available, and a smoke-control memo using a different fire zone.

## Power Playground Skill-Derived Task Candidates

These candidates translate the local `Power-Playground-main` SME review skills into this SSC. They are design-note candidates only; they do not add runnable templates, accepted evidence, or source-pack hardening.

| Candidate Task | Source Skill | Source Pack Shape | What The Check Should Catch |
| --- | --- | --- | --- |
| Can operators escape the switchroom during an arc-flash or fire event? | `substation-safe-design-assessment` | Switchroom GA object list, doors, door swings, equipment lineups, operating positions, egress route, and visible fire/emergency features. | The egress path passes through the hazard zone, door or equipment positions obstruct escape, or the response treats an unverified egress provision as proven. |
| Are the control and switching positions outside the worst hazard zone? | `substation-safe-design-assessment` | HMI/control panel location, switchgear face, likely operator stance, access path, and maintenance positions. | The task misses an operator-exposure hazard, invents remote switching, or fails to separate a real layout risk from a verification item. |
| Which expected safety provisions need verification before the SID workshop? | `substation-safe-design-assessment` | GA visible features plus verification log for emergency lighting, signage, detection, eyewash/spill response, ventilation, labels, and security. | Commonly expected items are either incorrectly raised as proven hazards or silently assumed to be present when the GA cannot verify them. |

## Checks The Template Should Catch

These checks make `SSC-08` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `floor_zone_model` source object or evidence artifact. | `ssc_08_source_identity_mismatch` |
| Scenario drift | One stage uses a different `population_basis` case without a case-selection record. | `ssc_08_scenario_mismatch` |
| Geometry or topology drift | `egress_routes` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_08_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_08_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_08_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_08_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_08_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_08_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_08_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_08_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-08-LH-01` Station Population, Vertical Movement, Egress, Alarm, And Ventilation Package: start here because it uses the main building occupancy and movement package source files and produces a source-pack-sized memo.
2. `SSC-08-LH-02` Room Occupancy, Lighting Energy, And Access-Control Package: add this after the first source pack has stable source files and control values.
3. `SSC-08-LH-03` Emergency Power For Life-Safety And Vertical Movement: add this after the first source pack has stable source files and control values.
4. `SSC-08-LH-04` Crowd, CCTV, And Communications Operations Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `building_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-08 product into a source pack.

A first executable-quality source pack for `SSC-08` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `building_source_manifest.yaml` | source fields such as `floor_zone_model`, `population_basis`, `egress_routes`, `vertical_transport`, `life_safety_loads` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `building_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `building_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as building occupancy and movement package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
