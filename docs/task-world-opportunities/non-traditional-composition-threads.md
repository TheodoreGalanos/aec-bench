# ABOUTME: Maps non-obvious cross-discipline task-world composition candidates.
# ABOUTME: Uses shared evidence surfaces and set-style operators to extend product-world design.

# Non-Traditional Composition Threads

This file is a companion to `combination-threads.md`.

`combination-threads.md` captures the natural engineering pipelines: hydrology to detention, pump duty to motor load, wind pressure to bracket load, and so on. This file looks for less obvious joins where two task worlds become one because they share an evidence surface, operating scenario, or authority chain.

The exhaustive all-card follow-up is `shared-subworld-cluster-scan.md`, with machine-readable outputs in `shared-subworld-cluster-scan.csv` and `shared-subworld-card-membership.csv`. That scan assigns all 184 task cards to path-keyed shared-subworld memberships and ranks 19 physical clusters plus one authority overlay using the rubric below.

The target pattern is not "put more tasks in a sequence." The target is a product world where the verifier can detect whether the same source artifact, geometry, standard assumption, or operating state is being preserved across disciplines.

## Operator Vocabulary

Use these as design shorthand:

| Operator | Meaning | Benchmark Use |
| --- | --- | --- |
| `projection pi_S(W)` | Select a view of a world, such as source-only, stage-only, drawing-only, or verifier-only. | Make easier variants or isolate a source-reading skill. |
| `subset W' subset W` | Remove sources, stages, disciplines, gates, or gaps. | Generate smaller variants without changing the authority story. |
| `intersection W1 cap_E W2` | Identify a shared evidence or assumption surface. | Find the drawing, profile, SLD, borehole log, schedule, or scenario both worlds must agree on. |
| `product W1 x_H W2` | Join worlds over named handoffs. | Compose stages where one world's output is another world's input. |
| `fiber product W1 x_S W2` | Join worlds over a shared subworld `S`, not only a scalar handoff. | Compose worlds through a common SLD, road profile, site plan, or operating scenario. |
| `difference W2 - W1` | Expose missing sources, changed assumptions, added gates, or regional overlays. | Compare variants and reveal what made a richer world harder. |
| `closure cl(W)` | Add deterministic consequences implied by the world. | Materialize derived handoffs, formula outputs, margins, and pass/fail records. |
| `boundary Required(W) - Available(W)` | Make the evidence gap explicit. | Separate benchmark-ready gaps from real-project-data gaps. |
| `repair(W, event)` | Add a distinction after a trace cannot be named by the current world. | Turn a failure into a new diagnostic, gate, or source requirement. |

The most interesting non-traditional operator is usually the fiber product. It composes two worlds over a shared subworld such as a vertical profile, electrical single-line diagram, borehole log, access plan, occupancy schedule, coastal flood envelope, or equipment layout.

## Task-Card Corpus Signals

The full task-card catalogue supports this search direction. A quick pass over `task-catalogue.csv` found:

| Signal | Count | Why It Matters |
| --- | ---: | --- |
| Built-in task cards | 184 | Large enough to search for cross-discipline surfaces rather than only hand-authored examples. |
| `source_geometry` operation handle | 184 | Every card can be projected into source/evidence space even if the current task is scalar. |
| `tabular-source` modality | 181 | Schedules, standards tables, and datasheets are the broadest shared authority surface. |
| `drawing-geometry` modality | 159 | Plans, profiles, sections, SLDs, layouts, and elevations can anchor shared-subworld products. |
| `spatial-map` modality | 57 | Site/corridor/coverage worlds are common enough to support spatial products. |
| `chart-curve` modality | 57 | Pump, acoustic, process, PV, wave, and equipment curves give cross-discipline curve handoffs. |
| `time-series` modality | 49 | Weather, load, flow, protection, and operating profiles can join worlds through scenario time. |
| `document-evidence` modality | 49 | Reports, permits, design notes, and criteria packs can carry authority across disciplines. |
| `hidden_parameter_policy` operation handle | 120 | Many cards already have a place to turn ambiguous source interpretation into explicit verifier state. |

Interpretation: the corpus is structurally ready for shared-subworld composition. The hard part is not finding enough possible joins. The hard part is selecting joins where the shared source surface is concrete enough for verification.

## Selection Rubric

Score candidate non-traditional products against these criteria before hardening one into a source pack:

| Criterion | Question | Strong Signal |
| --- | --- | --- |
| Shared-subworld concreteness | Is there one artifact or artifact family both worlds must preserve? | A long section, SLD, borehole log, layout, occupancy schedule, operating profile, or equipment schedule. |
| Cross-discipline distance | Does the composition cross a real discipline boundary rather than chaining same-family formulas? | Civil to electrical, process to acoustics, ground to arc-flash, storage to fire/containment. |
| Verifier locality | Can failures be localized to source extraction, invariant preservation, handoff, branch choice, or final calculation? | The product can name the broken join instead of only returning a low final score. |
| Source-pack realism | Would real projects naturally contain the required artifacts? | Owner drawings, schedules, design reports, equipment datasheets, logs, or calculations exist in ordinary delivery packs. |
| Event value | Would contradictions teach the meta-harness a new distinction? | Datum mismatch, grade sign drift, occupancy basis drift, electrical/mechanical load mismatch, or authority conflict. |
| Stage substrate | Are there enough existing task cards to cover meaningful stages? | At least three existing cards, preferably across two or more disciplines. |

Use the rubric to avoid a common failure mode: a clever conceptual composition that cannot be verified because the shared subworld is vague.

## Shared Evidence Surface Index

This is the useful search index for future passes.

| Shared Evidence Surface | Task-Card Families | Candidate Products | Key Invariants |
| --- | --- | --- | --- |
| Road vertical profile and long section | alignment geometry, roadway spread, HGL, culvert, signal timing, VMS | NTC-01, NTC-07 | chainage frame, datum, grade sign, surface level, design speed. |
| Electrical SLD, load schedule, and equipment layout | PV/BESS, voltage drop, feeder load, PoE, fault current, arc flash, pump/ventilation loads | NTC-01, NTC-04, NTC-10 | load basis, voltage level, feeder identity, protection assumptions, equipment location. |
| Borehole, groundwater, and resistivity records | soil interpretation, retaining, bearing, settlement, grid resistance, GPR | NTC-02 | groundwater case, depth/location frame, soil/resistivity distinction, foundation/grid geometry. |
| Coastal profile, tide/SLR table, and flood levels | wave runup, freeboard, outfall submergence, pump head, electrical elevation | NTC-03 | datum, planning horizon, design water level, equipment/floor/pad elevation. |
| Battery or hazardous equipment layout | BESS sizing, battery sizing, cable/feeder checks, fire/sprinkler, ventilation, bunding | NTC-04 | equipment inventory, energy/power distinction, containment volume, fire/ventilation authority. |
| Process basis and equipment schedule | oxygen demand, SRT, blower/pump power, feeder load, acoustic source level | NTC-05, NTC-10 | time basis, duty point, motor schedule, source-receiver geometry. |
| Piping alignment and transient scenario | headloss, pump duty, surge, thrust, pipe support, foundation, protection trip | NTC-06 | pipe segment identity, transient event, support location, motor trip/protection state. |
| Occupancy/population schedule and plan | occupant load, egress, lift/escalator capacity, NAC load, ventilation | NTC-08 | population basis, floor/zone membership, route identity, time/scenario class. |
| Roof/facade geometry | wind pressure, PV wind, gutter/downpipe, bracket load, construction tolerance | NTC-09 | zone geometry, roof/facade area, rainfall/wind region, fixing/support identity. |
| Corridor weather and route profile | OLE sag, conductor wind/ice, thermal stress, signal sighting, drainage/freeboard | NTC-12 | weather case, span/chainage identity, clearance envelope, speed/visibility basis. |

## Prioritization

Initial ranking for hardening:

| Rank | Candidate | Why It Rises | Main Risk |
| ---: | --- | --- | --- |
| 1 | NTC-01 road low-point drainage and field equipment resilience | Strong shared profile/long-section evidence, clear datum/grade invariants, and a vivid cross-discipline consequence. | Needs a source pack that ties field equipment location to drainage surfaces without overclaiming flood modelling. |
| 2 | NTC-02 soil/groundwater as structural and electrical safety medium | Uses ordinary project evidence and has high event value around soil/resistivity/groundwater distinctions. | Resistivity and geotechnical soil parameters are adjacent but not interchangeable; verifier must partition authority carefully. |
| 3 | NTC-04 BESS fire, containment, ventilation, and feeder package | Very real project shape and strong cross-discipline distance. | Public accepted project data may be sparse; may need task-owned redrawn layouts first. |
| 4 | NTC-05 wastewater blower process, power, and acoustic impact | Good bridge from process biology to electrical load and community impact. | Blower selection/source curve is the weak join unless a public datasheet or task-owned schedule is supplied. |
| 5 | NTC-08 station population, vertical movement, egress, alarm, and ventilation | Strong shared population basis and plan evidence. | Can become too broad unless scoped to one floor/zone and one scenario. |
| 6 | NTC-12 rail corridor weather across OLE, signalling, drainage, and thermal stress | Strong long-horizon flavor and rich event surface. | Standards and operator data access are harder than the first four candidates. |

## Candidate Threads

| ID | Candidate Product World | Composition Pattern | Shared Subworld | Task-Card Anchors | Why It Is Non-Traditional |
| --- | --- | --- | --- | --- | --- |
| NTC-01 | Road low-point drainage and field equipment resilience | `road_profile x_S stormwater x_S comms_power` | Road vertical profile, sag low points, pit surface levels, cabinet/equipment locations | `vertical-curve-design`, `roadway-spread`, `hgl-check`, `rational-method`, `poe-power-budget`, `voltage-drop` | A road geometry world becomes a drainage and electrical/communications resilience world, not just an alignment check. |
| NTC-02 | Soil and groundwater as structural stability plus electrical safety | `retaining_world x_S earthing_world` | Borehole logs, groundwater state, soil class, soil resistivity test area, substation/civil layout | `lateral-earth-pressure`, `retaining-wall-stability`, `wall-bearing`, `grid-resistance`, `incident-energy` | The same ground is both a mechanical load medium and an electrical fault-return/safety medium. |
| NTC-03 | Coastal flood, outfall, pump, and electrical elevation package | `coastal_world x_S pump_world x_S electrical_world` | Tide/SLR table, coastal profile, flood/freeboard level, pump-station section, equipment pad levels | `outfall-submergence-check`, `wave-runup`, `tidal-prism`, `pump-head-calculation`, `grid-resistance`, `voltage-drop` | Marine boundary conditions become both hydraulic constraints and electrical asset elevation/resilience constraints. |
| NTC-04 | BESS fire, containment, ventilation, and feeder package | `pv_storage_world x_S fire_life_safety x_S containment` | Battery/inverter layout, equipment datasheets, hazardous inventory, fire strategy, SLD, drainage isolation plan | `bess-sizing`, `battery-sizing`, `power-load-calculation`, `sprinkler-discharge`, `bund-volume-calculation`, `air-changes` | An energy-storage sizing world becomes a fire, spill, ventilation, and electrical protection world. |
| NTC-05 | Wastewater blower process, power, and acoustic impact package | `process_world x_H power_world x_S acoustic_world` | Process basis, blower schedule, motor schedule, plant layout, receiver plan | `oxygen-requirements`, `srt-calculation`, `pump-power-efficiency`, `power-load-calculation`, `distance-attenuation`, `a-weighting` | Oxygen demand generates electrical load and noise exposure; the bridge is equipment selection and site layout. |
| NTC-06 | Pipe transient, support, foundation, and motor trip package | `hydraulic_transient x_H structural_support x_S electrical_control` | Piping alignment, support layout, pump/motor schedule, operating transient scenario | `joukowsky-pressure`, `thrust-force-calculation`, `pipe-support-dead-load`, `wall-bearing`, `three-phase-fault-current` | A hydraulic event becomes a structural reaction and electrical/control-protection case. |
| NTC-07 | Visual operations package for road users, ITS, CCTV, and lighting | `road_geometry x_S visual_performance x_H comms_power` | Road speed environment, sign/camera/light locations, lighting grid, message library, network cabinet | `vms-legibility-distance`, `road-uniformity-check`, `road-aeci-calculation`, `ppm-calculation`, `poe-power-budget`, `yellow-interval-calculation` | Human legibility, lighting quality, camera recognition, communications bandwidth, and power headroom share the same corridor scene. |
| NTC-08 | Station population, vertical movement, egress, alarm, and ventilation | `occupancy_world x_H vertical_transport x_H life_safety` | Station plan, population schedule, lift/escalator schedule, egress routes, fire alarm zones, ventilation basis | `occupant-load`, `egress-width`, `handling-capacity`, `interval-calculation`, `escalator-capacity`, `nac-load-calculation`, `air-changes` | The same population is simultaneously a vertical-transport demand, evacuation demand, fire-alarm load, and ventilation basis. |
| NTC-09 | Roof/facade/PV wind, drainage, and access tolerance package | `wind_world x_S roof_drainage x_S facade_pv` | Roof/facade geometry, wind zones, drainage catchments, PV array layout, access/maintenance zones | `design-wind-speed`, `design-wind-pressure`, `solar-array-wind-load`, `gutter-sizing`, `downpipe-sizing`, `bracket-load-calc`, `construction-tolerance` | The same roof/facade geometry drives wind action, rainwater capacity, PV mounting loads, and tolerance/access constraints. |
| NTC-10 | Wastewater energy island: process loads, biogas, PV/BESS, and feeder | `treatment_world x_H energy_world x_S feeder_world` | Plant energy schedule, digester/gas record, PV/BESS layout, critical load list, feeder SLD | `biogas-production`, `sludge-production`, `oxygen-requirements`, `bess-sizing`, `dc-ac-ratio`, `radial-feeder-voltage-drop`, `pfc-sizing` | Treatment residuals become energy supply while process aeration remains a major electrical demand. |
| NTC-11 | Construction environmental controls, temporary traffic, and monitoring power | `construction_water_quality x_S temporary_traffic x_S comms_power` | Construction staging plan, catchment/erosion plan, temporary VMS/CCTV layout, site power/network cabinet | `sediment-basin-sizing`, `pollutant-load-estimate`, `vms-legibility-distance`, `cctv-storage-calculation`, `poe-power-budget`, `conduit-fill-calculation` | Temporary works combine environmental discharge, traffic communication, storage, and field power. |
| NTC-12 | Rail corridor weather: OLE sag, signalling sighting, drainage, and thermal stress | `rail_profile x_S weather_world x_H signalling_world` | Route profile, span schedule, weather table, signal layout, drainage/freeboard context | `single-span-sag-tension`, `wind-load-conductor`, `thermal-stress-calculation`, `signal-sighting-distance`, `warning-time-calculation`, `freeboard-calculation` | Weather and profile data affect electrical clearance, rail stress, signal sighting, warning time, and water-clearance risks. |

## Highest-Value Shortlist

These look most useful because they cross disciplines while still having stable source artifacts and verifier handles.

### 1. Road Low-Point Drainage And Field Equipment Resilience

Source pack:

- road alignment plan and long section;
- sag-vertical-curve and crossfall data;
- pit schedule and drainage long section;
- local catchment plan or inlet spacing table;
- field cabinet, VMS, CCTV, lighting, or signal controller locations;
- SLD/load schedule for powered field equipment.

Composition:

```text
vertical profile + crossfall
  -> low point, longitudinal slope, surface level
  -> gutter spread, inlet spacing, HGL clearance
  -> equipment flood/freeboard clearance and field power headroom
```

Verifier gates:

- grade sign convention is preserved from alignment to drainage;
- sag/low-point chainage matches the road profile;
- drainage catchment boundary matches the plan;
- HGL and roadway spread use the same surface level and slope basis;
- cabinet/equipment clearance is checked against the same flood/HGL surface;
- PoE/load schedule values are source-traceable, not guessed.

This is the strongest example of a non-obvious product: the road alignment world produces a drainage risk, and the drainage risk changes the validity of electrical/communications equipment placement.

### 2. Groundwater/Soil As Structural And Electrical Safety Medium

Source pack:

- borehole logs, CPT/SPT field sheets, lab summary tables;
- groundwater records and design water-state note;
- earthing soil-resistivity test records;
- substation or wall layout;
- retaining/foundation load summary;
- fault-current and protection basis.

Composition:

```text
soil interpretation and groundwater state
  -> earth pressure, bearing, settlement, uplift, wall stability
  -> apparent resistivity, grid resistance, GPR
  -> incident-energy/earthing safety package
```

Verifier gates:

- soil/groundwater scenarios are explicitly distinguished from resistivity assumptions;
- drained/undrained or sand/clay branch is not silently reused as an electrical soil class;
- wall/foundation geometry and substation grid geometry have separate drawing provenance;
- fault current and grid current remain electrically sourced;
- GPR, stability, and bearing outputs carry separate pass/fail criteria.

This is not just "ground feeds structure." It is the same physical site appearing under two different authorities: geotechnical stability and electrical safety.

### 3. BESS Fire, Containment, Ventilation, And Feeder Package

Source pack:

- BESS/battery/inverter datasheets;
- SLD and feeder/cable schedule;
- battery-room or container layout;
- fire strategy, sprinkler or suppression basis;
- ventilation schedule;
- hazardous inventory and drainage isolation/bund plan.

Composition:

```text
energy storage and critical load basis
  -> BESS capacity, feeder current, voltage drop, cable ampacity
  -> fire/suppression demand and ventilation load
  -> containment volume and drainage isolation checks
```

Verifier gates:

- battery energy, power, and usable capacity are not confused;
- fire/ventilation/containment source authority is separate from electrical sizing authority;
- connected load and critical load use the same time basis;
- containment inventory matches the layout and equipment schedule;
- SLD feeder/protection assumptions are available to downstream arc-flash or fault-current worlds.

This is a good "world product" because a storage system is simultaneously energy infrastructure, fire risk, environmental inventory, and electrical network element.

### 4. Wastewater Blower Process, Power, And Acoustic Impact

Source pack:

- influent/effluent load table;
- process flow diagram and basin schedule;
- blower/diffuser datasheets;
- electrical load list and motor schedule;
- site layout and boundary/receiver plan;
- acoustic criteria table.

Composition:

```text
process oxygen demand
  -> blower duty and motor power
  -> feeder/load schedule
  -> sound source level and receiver attenuation
```

Verifier gates:

- process loads preserve the same flow and concentration time basis;
- oxygen output is traceable into blower duty or stated as an unresolved selection gap;
- motor/electrical load list agrees with blower duty;
- acoustic source level is equipment-sourced, not inferred from power unless the rule is explicit;
- receiver distance comes from the site layout.

This is a good example of an engineering world that turns a biological/process requirement into an electrical and community-impact problem.

## Meta-Harness Implications

The task-world profile for these candidates needs more than a stage graph. It needs a shared-subworld declaration:

```yaml
composition:
  operator: fiber_product
  shared_subworld:
    id: road_vertical_profile
    source_artifacts:
      - alignment_plan
      - long_section
      - drainage_long_section
    invariants:
      - chainage_frame
      - datum
      - grade_sign_convention
  joined_worlds:
    - road_alignment
    - stormwater_hydraulics
    - field_equipment_power
```

Useful verifier additions:

- `shared_subworld_manifest`: source artifacts, coordinate/datum/chainage frames, and owners.
- `cross_world_invariants`: values that must remain identical or consistently transformed.
- `handoff_contracts`: scalar handoffs with units, source, precision, and consumer.
- `authority_partitions`: which standard or discipline owns each decision.
- `conflict_ledger`: contradictions that should be contained rather than collapsed.
- `repair_events`: missing handoff, source contradiction, silent branch change, or impossible downstream value.

## Relationship To Existing Product Worlds

The ten current long-horizon product worlds already prove the basic composite substrate. This file is about second-order composition:

- `stormwater-drainage-package` can compose with road geometry and field equipment resilience through low-point and flood-clearance evidence.
- `civil-ground-retaining-interface` can compose with `earthing-arc-flash-package` through soil, groundwater, and site layout evidence.
- `pv-storage-feeder-package` can compose with fire, containment, and ventilation worlds through battery layout and hazardous inventory evidence.
- `treatment-aeration-power-package` can compose with acoustic, feeder, and site-layout worlds through blower duty.
- `road-rail-alignment-package` and `rail-braking-signalling-package` can compose with weather, OLE, lighting, and ITS worlds through a corridor profile and operating-speed subworld.

The benchmark lesson is that non-traditional compositions should be selected by shared evidence surfaces first and scalar handoffs second. If the shared subworld is weak, the composition will be a bag of tasks. If the shared subworld is explicit, the composition becomes a real product world.
