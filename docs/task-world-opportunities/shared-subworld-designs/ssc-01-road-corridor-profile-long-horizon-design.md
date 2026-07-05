# SSC-01 Road/corridor profile and traffic scene Long-Horizon Design

This document treats the road corridor as one design package: the same chainage, levels, crossfalls, intersections, roadside equipment, and operating assumptions have to line up. A useful exercise here keeps that corridor identity stable while moving between road geometry, drainage, sight distance, traffic signals, ITS communications, cabinet power, and owner review decisions.

## Evidence Basis

| Field | Value |
| --- | --- |
| Corridor source state | road vertical profile, chainage, crossfall, road speed, intersections, roadside equipment |
| Memberships | 18 task-card memberships |
| Primary cards | 9 |
| Disciplines | civil, electrical, mechanical |
| Score | 29/30 |
| Candidate product | Road low-point drainage and field equipment resilience |
| Main risk | Needs a profile/drainage/equipment source pack without overclaiming full flood modelling. |

The current component checks are ordinary road, traffic, drainage, roadside-structure, communications, and interchange calculations:

| Card | Plain-language role |
| --- | --- |
| `curve-elements` | Works out horizontal curve geometry and the chainages where the curve starts and ends. |
| `design-wind-pressure` | Turns wind assumptions into pressure on exposed roadside items such as signs, poles, cabinets, or screens. |
| `driveway-gradient-check` | Checks whether a driveway or access connection is too steep for the expected vehicle movement. |
| `intersection-sight-distance` | Checks whether a driver can see far enough at an intersection before entering or crossing traffic. |
| `min-curve-radius` | Finds the smallest road curve radius that is acceptable for the design speed and road crossfall. |
| `ssd-on-grade` | Checks stopping distance on an uphill or downhill road grade. |
| `superelevation-rate` | Checks the crossfall used to help vehicles negotiate a horizontal curve. |
| `all-red-interval-calculation` | Sets the traffic-signal clearance time after one movement stops and before the next starts. |
| `bandwidth-calculation` | Checks whether the ITS network has enough capacity for devices such as CCTV, VMS, and traffic controllers. |
| `handling-capacity` | Estimates people-moving capacity; it belongs here only when the road corridor includes a station, lift, or interchange access element. |

## Corridor Data Model

Treat each task as a check against the same corridor source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted corridor data, calculations, design response, audit trail}
```

For `SSC-01`, the corridor source state is:

```text
S_ssc_01 = {
  chainage_frame,
  vertical_profile,
  surface_and_crossfall,
  drainage_assets,
  roadside_equipment,
  traffic_scenario,
  power_comms_boundary,
  authority_partition,
}
```

The product combinations below share the same corridor data. A change to chainage, level, crossfall, drainage, equipment, or traffic scenario must carry through each check.

```text
W_ssc01_lh_01 x_S W_ssc01_lh_02
W_ssc01_lh_02 x_S W_ssc01_lh_03
W_ssc01_lh_03 x_S W_ssc01_lh_04
W_ssc01_lh_04 x_S W_ssc01_lh_05
W_ssc01_lh_05 x_S W_ssc01_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted corridor data, calculations, final response, and audit trail. |
| `S_ssc_01` | The corridor source state that all combined checks must agree on. |
| `W_ssc01_lh_01` | The first SSC-01 long-horizon product below, road low-point drainage and field equipment resilience. |
| `x_S` | Combine two checks while forcing them to use the same corridor source state `S_ssc_01`. |

For example, `W_ssc01_lh_01 x_S W_ssc01_lh_02` means the drainage/equipment-resilience product and the intersection timing/sight-distance product must agree on the same road profile, chainage frame, grades, and scenario. If one side moves the low point or changes the design speed, the other side must either inherit that change or flag a source conflict.

The check is whether the same drawing, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Corridor Source Manifest

Any `SSC-01` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `chainage_frame` | Single route stationing basis for all geometry, pits, devices, and sight-distance objects. | alignment plan, long section, survey control |
| `vertical_profile` | Sag/crest profile, grade signs, vertical curves, and low points. | road long section, design model export |
| `surface_and_crossfall` | Lane/crossfall/surface elevation state used by drainage and safety checks. | cross sections, pavement model |
| `drainage_assets` | Pits, gutters, spread zones, culverts, HGL points, and outfalls tied to chainage. | drainage long section, pit schedule |
| `roadside_equipment` | Cabinets, VMS, CCTV, signals, lighting, poles, and power/comms cabinets. | ITS/electrical layout, equipment schedule |
| `traffic_scenario` | Speed, stopping sight, pedestrian timing, queue, incident, or night/storm operating case. | traffic criteria, signal timing sheet |
| `power_comms_boundary` | Feeder, PoE, battery, network, and cabinet limits for roadside equipment. | SLD, network topology, power schedule |
| `authority_partition` | Road, drainage, electrical, ITS, and traffic authorities for each gate. | criteria matrix, owner notes |

## Candidate Long-Horizon Products

### SSC-01-LH-01: Road Low-Point Drainage And Field Equipment Resilience

Use this package when a sag point in the road profile sits near cabinets, signals, or other field equipment. The source files need to show the road long section, drainage assets, and equipment setout on the same chainage and level basis.

The engineer checks whether water reaches the road or the equipment, then checks whether the equipment still has usable power and communications during the event. The output should name the controlling low point, storm case, exposed asset, and follow-on drawing or schedule changes.

Work sequence:

```text
road profile low point and crossfall
  -> pit, gutter, spread, and HGL check
  -> cabinet or signal asset elevation
  -> backup power and communications consequence
  -> resilience design memo
```

Engineering checks in this package:

| Check | What An Engineer Is Checking |
| --- | --- |
| `curve-elements` | The horizontal curve and chainage setout around the low point, so pits, cabinets, and sight lines are all located against the same road geometry. |
| `ssd-on-grade` | Whether a driver has enough stopping distance on the grade approaching the sag point, especially when water or poor visibility is part of the scenario. |
| `roadway-spread` | How far stormwater spreads across the lane or shoulder before it reaches a pit, gutter, or low point. |
| `hgl-check` | Whether the pipe or pit hydraulic grade line rises high enough to surcharge, flood the pavement, or threaten nearby roadside equipment. |
| `vms-legibility-distance` | Whether a driver can read a variable message sign early enough to react before reaching the affected low point or closure area. |
| `battery-sizing` | Whether the roadside cabinet has enough backup energy to keep the required equipment running through the selected storm or outage case. |

Source pack:

- road alignment plan and long section;
- pit, pipe, gutter, and HGL schedule;
- ITS/signal/cabinet layout;
- cabinet load and backup schedule;
- road authority drainage and traffic criteria.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change road alignment plan and long section while keeping the downstream pit, gutter, spread, and HGL check fixed. | Confirms the road profile and selected design case are recorded before the result changes. |
| Source conflict | Make road alignment plan and long section disagree with pit, pipe, gutter, and HGL schedule about the controlling value or object. | Confirms which drawing or schedule controls the chainage. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in ITS/signal/cabinet layout only. | Confirms the asset location, road surface, and crossfall are kept consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the road, drainage, electrical, ITS, or owner criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when a road low point, drainage asset, and roadside cabinet all depend on the same chainage and level datum. The response should show where water goes, which asset is exposed, and what backup power or communications consequence follows.

### SSC-01-LH-02: Intersection Timing, Grade, And Sight-Distance Package

Use this package when an intersection approach has grade, sight-distance, and signal-timing issues tied to the same layout. The source files need the approach IDs, vertical profile, speed criteria, and signal timing sheet in one place.

The engineer checks whether drivers and pedestrians have enough sight, warning, and clearance time for that approach. The output should name the controlling approach, vehicle or pedestrian case, and timing values that change.

Work sequence:

```text
approach profile and grade sign convention
  -> design speed and stopping/sight-distance check
  -> yellow, all-red, and pedestrian clearance timing
  -> wet/night or heavy-vehicle scenario
  -> traffic-safety memo
```

Engineering checks in this package:

| Check | What An Engineer Is Checking |
| --- | --- |
| `intersection-sight-distance` | Whether drivers at the intersection can see far enough along the road to enter, turn, or cross without an unsafe conflict. |
| `ssd-on-grade` | Whether the approach grade changes the stopping distance enough to affect the signal timing or safety case. |
| `all-red-interval-calculation` | The clearance time after one movement receives red, so vehicles already in the intersection can leave before another movement starts. |
| `yellow-interval-calculation` | The warning time before red, based on approach speed, grade, and driver reaction assumptions. |
| `pedestrian-clearance-time` | Whether pedestrians have enough time to cross before conflicting traffic is released. |

Source pack:

- intersection plan with approach IDs;
- vertical profile and survey datum;
- signal timing sheet;
- speed and vehicle criteria;
- sight-distance obstruction notes.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change intersection plan with approach IDs while keeping the downstream design speed and stopping/sight-distance check fixed. | Confirms the road profile and selected design case are recorded before the result changes. |
| Source conflict | Make intersection plan with approach IDs disagree with vertical profile and survey datum about the controlling value or object. | Confirms which drawing or schedule controls the chainage. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in signal timing sheet only. | Confirms the asset location, road surface, and crossfall are kept consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the road, drainage, electrical, ITS, or owner criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when approach grade, design speed, sight distance, and signal clearance time are all tied to the same intersection layout. The response should make the controlling approach, vehicle case, and timing basis explicit.

### SSC-01-LH-03: Road Lighting, ITS, And Drainage Operations Scene

Use this package when lighting, cameras, signs, network capacity, and cabinet power all sit on one road segment. The source files need to locate each device against the road layout, lighting grid, cabinet schedule, and network topology.

The engineer checks whether night or storm operation changes the lighting, data, storage, PoE, or supply assumptions. The output should trace each device to a chainage, cabinet, and operating case.

Work sequence:

```text
road segment and lighting grid
  -> VMS/CCTV/network device register
  -> storm or night operating scenario
  -> power and bandwidth rollup
  -> operations continuity note
```

Engineering checks in this package:

| Check | What An Engineer Is Checking |
| --- | --- |
| `road-uniformity-check` | Whether lighting is even enough along the road segment, instead of leaving dark patches near devices, crossings, or conflict points. |
| `road-pdi-calculation` | Whether the lighting layout creates too much disability glare for drivers using the corridor at night. |
| `bandwidth-calculation` | Whether the ITS network can carry the combined CCTV, VMS, detector, and controller traffic during the selected operating case. |
| `cctv-storage-calculation` | Whether the video system has enough storage for the camera resolution, frame rate, retention period, and number of cameras. |
| `poe-power-budget` | Whether the network switch or injector can supply enough power to PoE cameras, radios, or roadside devices after cable losses and spare capacity. |

Source pack:

- road layout and lighting grid;
- VMS and CCTV schedule;
- network topology and fibre/radio links;
- local SLD or cabinet schedule;
- surface-water or storm-risk note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change road layout and lighting grid while keeping the downstream VMS/CCTV/network device register fixed. | Confirms the road profile and selected design case are recorded before the result changes. |
| Source conflict | Make road layout and lighting grid disagree with VMS and CCTV schedule about the controlling value or object. | Confirms which drawing or schedule controls the chainage. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in network topology and fibre/radio links only. | Confirms the asset location, road surface, and crossfall are kept consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the road, drainage, electrical, ITS, or owner criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the lighting layout, VMS/CCTV schedule, network capacity, cabinet supply, and storm scenario all describe the same road segment. The response should make every device traceable to its chainage and cabinet.

### SSC-01-LH-04: Emergency Detour And Roadside Device Continuity

Use this package when a closure or emergency detour relies on roadside signs, cameras, radios, and powered cabinets. The source files need the closure scenario, detour route, message library, device inventory, and backup supply.

The engineer checks whether the signs can be read, the communications path works, and the equipment stays powered for the closure duration. The output should show that every device used in the response exists in the inventory and supports the selected detour.

Work sequence:

```text
incident or closure scenario
  -> detour path and message library
  -> VMS/CCTV/device membership
  -> backup supply and comms topology
  -> operations continuity response
```

Engineering checks in this package:

| Check | What An Engineer Is Checking |
| --- | --- |
| `vms-legibility-distance` | Whether a detour message can be read soon enough for drivers to change lane, slow down, or leave the route safely. |
| `bandwidth-calculation` | Whether the available network can support the cameras, signs, and controllers needed during the closure. |
| `rf-link-budget` | Whether a wireless link has enough signal margin for the detour device or temporary communications path. |
| `battery-sizing` | Whether the device or cabinet can operate for the required detour duration without mains power. |
| `voltage-drop` | Whether the feeder voltage at the roadside device stays within limits when the detour equipment is running. |

Source pack:

- detour plan;
- device inventory and message library;
- network and power topology;
- traffic management plan;
- battery or generator schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change detour plan while keeping the downstream detour path and message library fixed. | Confirms the road profile and selected design case are recorded before the result changes. |
| Source conflict | Make detour plan disagree with device inventory and message library about the controlling value or object. | Confirms which drawing or schedule controls the chainage. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in network and power topology only. | Confirms the asset location, road surface, and crossfall are kept consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the road, drainage, electrical, ITS, or owner criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when a detour plan depends on a known set of signs, VMS boards, CCTV views, cabinets, and network links. The response should prove that the response uses the devices that actually support the closure scenario.

### SSC-01-LH-05: Bus Priority, Signal Corridor, And Cabinet Load Package

Use this package when a bus-priority corridor changes signal timing, detectors, controller equipment, and cabinet loading together. The source files need the signal phasing, detector locations, controller schedule, cabinet feeder, and operating criterion.

The engineer checks whether the traffic priority case and the electrical load case describe the same equipment. The output should connect the selected bus-priority scenario to clearance times, cabinet load, voltage drop, and any schedule changes.

Work sequence:

```text
priority corridor and signal group identity
  -> approach timing and queue case
  -> controller and detector load schedule
  -> feeder or backup supply check
  -> traffic-priority design response
```

Engineering checks in this package:

| Check | What An Engineer Is Checking |
| --- | --- |
| `all-red-interval-calculation` | The intersection clearance time needed before the next signal phase can safely start. |
| `yellow-interval-calculation` | The warning time for the bus-priority approach, using the same speed and grade assumptions as the traffic case. |
| `handling-capacity` | Whether the corridor or interchange access can move the expected number of people during the selected bus-priority scenario. |
| `power-load-calculation` | The total load from controllers, detectors, signs, and communications equipment in the cabinet. |
| `voltage-drop` | Whether the feeder voltage at the cabinet and connected devices remains acceptable under the selected load. |

Source pack:

- signal phasing and priority plan;
- controller/detector equipment schedule;
- corridor load schedule;
- cabinet feeder schedule;
- owner operations criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change signal phasing and priority plan while keeping the downstream approach timing and queue case fixed. | Confirms the road profile and selected design case are recorded before the result changes. |
| Source conflict | Make signal phasing and priority plan disagree with controller/detector equipment schedule about the controlling value or object. | Confirms which drawing or schedule controls the chainage. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in corridor load schedule only. | Confirms the asset location, road surface, and crossfall are kept consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the road, drainage, electrical, ITS, or owner criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when bus priority, signal phasing, controller equipment, detectors, and cabinet loads share the same corridor device list. The response should connect the traffic case to the electrical load case without renaming devices.

### SSC-01-LH-06: Culvert, Driveway Access, And Safety Continuity Package

Use this package when a driveway or local-road access point is controlled by the same grade, sight-distance, and drainage conditions. The source files need the access profile, culvert or gutter schedule, surface levels, tailwater, and access criteria.

The engineer checks whether the access stays usable and visible during the selected storm or vehicle case. The output should name the controlling access point, drainage case, sight line, and any level or grading change.

Work sequence:

```text
driveway or local-road profile
  -> culvert or gutter conveyance
  -> sight-distance and grade-compliance check
  -> flooded-access scenario
  -> access-safety memo
```

Engineering checks in this package:

| Check | What An Engineer Is Checking |
| --- | --- |
| `driveway-gradient-check` | Whether the access grade is usable for the expected vehicles without scraping, grounding, or creating an unsafe tie-in. |
| `culvert-capacity` | Whether the culvert can pass the selected storm flow without backing water up over the access or road edge. |
| `roadway-spread` | Whether runoff spreads into the traffic lane, shoulder, or driveway path beyond the allowed width. |
| `intersection-sight-distance` | Whether drivers leaving the driveway or local road can see approaching traffic clearly enough. |
| `freeboard-calculation` | Whether there is enough level difference between the design water surface and the road, driveway, or structure that must stay clear. |

Source pack:

- driveway profile and local road chainage;
- culvert or gutter schedule;
- surface elevation and tailwater table;
- access criteria;
- traffic/sight-distance assumptions.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change driveway profile and local road chainage while keeping the downstream culvert or gutter conveyance fixed. | Confirms the road profile and selected design case are recorded before the result changes. |
| Source conflict | Make driveway profile and local road chainage disagree with culvert or gutter schedule about the controlling value or object. | Confirms which drawing or schedule controls the chainage. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in surface elevation and tailwater table only. | Confirms the asset location, road surface, and crossfall are kept consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the road, drainage, electrical, ITS, or owner criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when a driveway or local-road access point may fail because the same low point controls grade, sight distance, and drainage. The response should stop short of full flood modelling unless the source files actually support it.

### SSC-01-LH-07: Roadside Cabinet Flood, Heat, And Backup Energy Package

Use this package when a roadside cabinet has to keep operating through flood, heat, or power-outage conditions. The source files need the cabinet setout, level detail, HGL or inundation table, enclosure derating note, load schedule, and access note.

The engineer checks whether the cabinet is exposed, derated, underpowered, or inaccessible in the selected event. The output should tie the serviceability decision to the cabinet location, event case, load, battery or BESS sizing, and feeder limits.

Work sequence:

```text
cabinet location and elevation
  -> storm/HGL or heat scenario
  -> critical load and autonomy register
  -> feeder or solar/battery check
  -> resilience exception memo
```

Engineering checks in this package:

| Check | What An Engineer Is Checking |
| --- | --- |
| `battery-sizing` | Whether the cabinet battery can run the critical loads for the required outage duration. |
| `bess-sizing-basic` | Whether a larger battery system has enough power and energy capacity for the cabinet or roadside-equipment group. |
| `voltage-drop` | Whether supply voltage stays within limits at the cabinet after cable length, load, and operating case are accounted for. |
| `hgl-check` | Whether the drainage system or flood level reaches the cabinet base, cable entry, or maintenance access. |
| `road-aeci-calculation` | Whether the road-lighting energy use is consistent with the lighting area and expected annual operation. |

Source pack:

- cabinet setout and elevation detail;
- HGL or inundation table;
- temperature or enclosure derating note;
- load and battery schedule;
- maintenance/access note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change cabinet setout and elevation detail while keeping the downstream storm/HGL or heat scenario fixed. | Confirms the road profile and selected design case are recorded before the result changes. |
| Source conflict | Make cabinet setout and elevation detail disagree with HGL or inundation table about the controlling value or object. | Confirms which drawing or schedule controls the chainage. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in temperature or enclosure derating note only. | Confirms the asset location, road surface, and crossfall are kept consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the road, drainage, electrical, ITS, or owner criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when a roadside cabinet has to stay serviceable during flood, heat, or outage conditions. The response should tie cabinet setout, HGL or heat case, load schedule, battery sizing, and access notes to the same location.

### SSC-01-LH-08: Multimodal Corridor Review Response Package

Use this package when a reviewer comment changes a corridor assumption and several disciplines have to update their calculations together. The source files need the comment register, road/drainage/ITS source index, marked-up plan or long section, authority criteria, and change ledger.

The engineer identifies which source changed, which calculations must be rerun, and which drawings or schedules move as a result. The output should make the response traceable from comment to source change to recalculation.

Work sequence:

```text
corridor source pack and review comments
  -> changed chainage or scenario assumption
  -> discipline-specific recalculations
  -> authority response table
  -> revised design memo
```

Engineering checks in this package:

| Check | What An Engineer Is Checking |
| --- | --- |
| `curve-elements` | Whether a changed plan or comment moves the curve setout, chainage, or reference point used by the rest of the corridor package. |
| `hgl-check` | Whether the revised drainage assumption changes surcharge, flooding, or level clearance at the affected location. |
| `pedestrian-clearance-time` | Whether a changed crossing, signal phase, or review comment affects the pedestrian clearance time. |
| `vms-legibility-distance` | Whether a changed sign location or message plan still gives drivers enough distance to read and react. |
| `voltage-drop` | Whether the revised device, cabinet, or feeder arrangement still supplies acceptable voltage at the affected equipment. |

Source pack:

- comment register;
- road/drainage/ITS source index;
- redrawn plan and long section;
- authority criteria matrix;
- change ledger.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change comment register while keeping the downstream changed chainage or scenario assumption fixed. | Confirms the road profile and selected design case are recorded before the result changes. |
| Source conflict | Make comment register disagree with road/drainage/ITS source index about the controlling value or object. | Confirms which drawing or schedule controls the chainage. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in redrawn plan and long section only. | Confirms the asset location, road surface, and crossfall are kept consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the road, drainage, electrical, ITS, or owner criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when a reviewer comment changes one corridor assumption and the response has to repair the drainage, traffic, ITS, and power consequences together. The response should show exactly which source changed and which calculations were rerun.

## How The Variants Come Together

All `SSC-01` variants should use the same corridor workflow:

```text
source file register
  -> corridor source table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the corridor package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-01-LH-01` | Road Low-Point Drainage And Field Equipment Resilience | `chainage_frame` | Keeps the same stationing across the road profile, drainage table, and cabinet location. |
| `SSC-01-LH-02` | Intersection Timing, Grade, And Sight-Distance Package | `vertical_profile` | Keeps the same approach grade and design-speed case across sight-distance and signal timing checks. |
| `SSC-01-LH-03` | Road Lighting, ITS, And Drainage Operations Scene | `surface_and_crossfall` | Keeps the same road surface and crossfall across lighting, device, and storm-operation checks. |
| `SSC-01-LH-04` | Emergency Detour And Roadside Device Continuity | `drainage_assets` | Keeps the same drainage risk and device list across detour messaging and operations checks. |
| `SSC-01-LH-05` | Bus Priority, Signal Corridor, And Cabinet Load Package | `roadside_equipment` | Keeps the same controller, detector, and cabinet identities across traffic and electrical checks. |
| `SSC-01-LH-06` | Culvert, Driveway Access, And Safety Continuity Package | `traffic_scenario` | Keeps the same access and vehicle case across drainage, grade, and sight-distance checks. |
| `SSC-01-LH-07` | Roadside Cabinet Flood, Heat, And Backup Energy Package | `power_comms_boundary` | Keeps the same cabinet supply and communications limits across storm, heat, and outage checks. |
| `SSC-01-LH-08` | Multimodal Corridor Review Response Package | `authority_partition` | Keeps the same owner, road, drainage, ITS, and electrical criteria visible during review response. |

The corridor package should keep the same profile, chainage, crossfall, speed, intersection layout, and roadside equipment list across the drainage, traffic, ITS, power, and review checks.

## Domain Practice Notes

Real-world fit:

- Treat this as a corridor operations/design package: road geometry, drainage low points, traffic-control devices, field equipment, power, and communications. Real tasks include plan/profile design, sight-distance checks, intersection clearance timing, drainage spread/HGL, ITS cabinet placement, detour messaging, bus priority, and authority review.
- The products are realistic because road-corridor reviews often fail at shared chainage, datum, device identity, or scenario control rather than formula difficulty.
- The note should require a corridor source register with chainage, datum, design speed, lane geometry, drainage structures, device IDs, cabinet/electrical IDs, traffic scenario, and authority criteria.

Typical practitioner steps:

1. Build the corridor baseline from survey/model/alignment files, plan/profile drawings, drainage long sections, signal/ITS layouts, and criteria.
2. Run geometry, safety, traffic, drainage, device, power, and communications checks against the same location and scenario.
3. Compare review or operating scenarios, such as storm event, closure, bus priority, cabinet outage, or authority-rule change.
4. Issue a memo or schedule listing the controlling approach, location, device, and drawing/timing/schedule changes.

Software stack notes:

- [OpenRoads Designer](https://www.bentley.com/software/openroads-designer/) is a realistic corridor design anchor because it joins surveying, drainage, utilities, roadway design, alignments, profiles, cross-sections, stormwater drainage, and corridor modelling.
- [MUTCD](https://mutcd.fhwa.dot.gov/) is a realistic U.S. traffic-control source for markings, signs, and signals. It should be treated as one authority regime, not as a global road-design standard.
- [PTV Vissim](https://www.ptvgroup.com/en/products/ptv-vissim) is a realistic microsimulation anchor for intersection/corridor scenarios, multimodal interactions, and signal or operations testing.
- [EPA SWMM](https://www.epa.gov/water-research/storm-water-management-model-swmm) is a realistic drainage/hydraulic modelling anchor when road low points tie to HGL, spread, storage, or outlet behaviour.

Design implications:

- Add `corridor_source_register`, `device_inventory`, and `scenario_register` fields before hardening `SSC-01-LH-01`.
- Keep road/drainage/ITS/electrical device IDs stable across product sections; do not let a memo rename the cabinet, pit, sign, or approach.
- Negative cases should include a chainage/datum mismatch, a device inventory mismatch, and a traffic scenario reused for the wrong storm or closure case.

## Review-Loop Lens From SME Skills

The Power Playground skills add a useful construction lens for this note: `SSC-01` can be framed as a corridor issue-readiness review, not only as a sequence of drainage, traffic, ITS, and cabinet-power calculations. The existing eight products stay intact; this section describes what the review-loop pattern adds to the analysis.

Review-loop fit:

- A road corridor package often fails because source objects drift: the pit, cabinet, VMS, signal approach, low point, or review comment is not the same object across drawings, schedules, calculations, and memos.
- The useful long-horizon question can be: "Is this corridor operations package ready to issue, and what must be fixed before it is issued?"
- Missing data should be an explicit output. If the package does not show the cabinet elevation, signal timing revision, drainage HGL basis, or device power boundary, the correct response is an information request rather than a guessed pass.
- The final artifact can be a completed corridor review matrix, findings memo, and action register instead of a single design memo.

Example review-loop task:

```text
corridor source packet
  -> inventory plan/profile, drainage, signal, ITS, power, and authority files
  -> extract chainage, datum, low point, device IDs, storm case, traffic scenario, and power/comms boundary
  -> mark corridor review items as pass, fail, not applicable, or insufficient data
  -> produce critical findings, information requests, and action register
  -> verify every fail and missing-data item is closed or carried forward
```

Source packet shape:

- road alignment plan, long section, and cross-section or surface model extract;
- drainage long section, pit schedule, pipe/HGL table, and low-point spread result;
- traffic scenario, signal timing sheet, sight-distance assumptions, and review comments;
- ITS/electrical layout, cabinet/device schedule, network/power schedule, and battery runtime basis;
- authority criteria matrix and comment register.

What this adds to verifier design:

- Check that every major source file and revision is inventoried before conclusions.
- Check that chainage, datum, device ID, pit ID, signal approach, and scenario ID stay stable across all outputs.
- Check that each review item has one explicit status: pass, fail, not applicable, or insufficient data.
- Check that every failure has a source citation, consequence, and action.
- Check that every insufficient-data item names the exact missing source or field.
- Check that the memo does not claim authority approval, full compliance, accepted project evidence, or benchmark readiness.

This lens makes `SSC-01` feel more like a real corridor design review. It turns the long-horizon challenge from "do more calculations" into "maintain source identity, expose gaps, prioritize fixes, and produce an auditable issue-readiness packet."

## Checks The Template Should Catch

These checks make `SSC-01` more than a stack of separate road and ITS calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `chainage_frame` source object or evidence artifact. | `ssc_01_source_identity_mismatch` |
| Scenario drift | One stage uses a different `vertical_profile` case without a case-selection record. | `ssc_01_scenario_mismatch` |
| Geometry or topology drift | `surface_and_crossfall` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_01_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_01_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_01_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_01_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_01_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_01_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_01_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_01_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-01-LH-01` Road Low-Point Drainage And Field Equipment Resilience: start here because one profile, drainage table, cabinet layout, and backup-power schedule can prove the corridor state is stable.
2. `SSC-01-LH-02` Intersection Timing, Grade, And Sight-Distance Package: add this after the profile and chainage controls are reliable.
3. `SSC-01-LH-03` Road Lighting, ITS, And Drainage Operations Scene: add this once device locations, network loads, and surface-water assumptions can share the same corridor plan.
4. `SSC-01-LH-04` Emergency Detour And Roadside Device Continuity: add this once the device list, power topology, and traffic management plan can be tied to one closure scenario.

The next artifact should be a `corridor_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, corridor keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-01 product into a source pack.

A first executable-quality source pack for `SSC-01` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `corridor_source_manifest.yaml` | corridor fields such as `chainage_frame`, `vertical_profile`, `surface_and_crossfall`, `drainage_assets`, `roadside_equipment` | Defines the corridor data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated corridor manifest, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `corridor_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as road-corridor product notes, while the source-pack build notes should be used only to guide later fixture packaging.
