# SSC-16 Construction, temporary works, environmental controls, and staging world Long-Horizon Design

This document treats construction staging as one source-controlled site package: staging plan, temporary works, erosion controls, traffic controls, environmental limits, monitoring, temporary power, and hold points have to line up. A useful long-horizon task keeps that construction basis consistent while moving between temporary works, sediment controls, traffic, power, monitoring, tolerance, and inspection checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Construction source state | construction staging plan, erosion/sediment controls, temporary traffic/comms/power, site monitoring |
| Memberships | 8 task-card memberships |
| Primary cards | 2 |
| Disciplines | civil, electrical, structural |
| Score | 23/30 |
| Candidate product | Construction environmental controls, temporary traffic, and monitoring power package |
| Main risk | Temporary works artifacts vary widely and can become scenario prose without drawings. |

The current card anchors cover temporary works, erosion and sediment, construction tolerance, temporary power, traffic, monitoring, and site-control checks:

| Card | Plain-language role |
| --- | --- |
| `bund-volume-calculation` | Oil containment bund volume calculation per AS/NZS 1940. |
| `cerc-longshore-transport` | Longshore sediment transport rate using the CERC formula Q_l = K * (E*Cg)_b * sin(2*alpha_b) / (2 * (rho_s - rho_w) * g * (1 - p)). |
| `design-wind-speed` | Site wind speed V_sit,beta from regional speed and multipliers per AS/NZS 1170.2. |
| `freeboard-calculation` | Freeboard calculation for coastal/flood structures: total freeboard = wave_allowance + slr_allowance + construction_tolerance + safety_margin (NZS 4404 / MfE Guidance). |
| `pollutant-load-estimate` | Estimate annual pollutant loads from a catchment using the EMC method. |
| `sediment-basin-sizing` | Size construction sediment basin per Blue Book (Soils and Construction). |
| `string-sizing` | Solar PV string sizing with temperature-corrected voltage limits per AS/NZS 5033. |
| `construction-tolerance` | Construction tolerance allowance and required slot length calculation. |

## Construction Staging Data Model

Treat each task as a check against the same construction staging package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-16`, the construction staging package source state is:

```text
S_ssc_16 = {
  stage_id,
  temporary_geometry,
  environmental_controls,
  temporary_traffic_devices,
  temporary_power_comms,
  weather_event,
  handover_state,
  authority_partition,
}
```

The product combinations below share the same construction staging package data. A change to staging plan, temporary works layout, erosion control, traffic control, environmental limit, monitoring point, temporary supply, or hold point must carry through each check.

```text
W_ssc16_lh_01 x_S W_ssc16_lh_02
W_ssc16_lh_02 x_S W_ssc16_lh_03
W_ssc16_lh_03 x_S W_ssc16_lh_04
W_ssc16_lh_04 x_S W_ssc16_lh_05
W_ssc16_lh_05 x_S W_ssc16_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_16` | The construction staging package source state that all combined checks must agree on. |
| `W_ssc16_lh_01` | The first SSC-16 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same construction staging package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Construction Source Manifest

Any `SSC-16` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `stage_id` | Construction stage, date, work zone, traffic phase, and active temporary works. | staging plan |
| `temporary_geometry` | Diversions, excavations, stockpiles, basins, access roads, barriers, supports. | temporary works drawing |
| `environmental_controls` | Sediment basin, pollutant control, dewatering, spill, monitoring, and discharge points. | ESCP/environmental plan |
| `temporary_traffic_devices` | Signs, VMS, CCTV, lighting, barriers, and lane closures. | traffic management plan |
| `temporary_power_comms` | Generators, batteries, temporary boards, PoE, telemetry, and monitoring power. | temporary services plan |
| `weather_event` | Rain, wind, tide, heat, or construction shutdown event. | weather/design basis |
| `handover_state` | What is temporary, permanent, active, inactive, removed, or commissioned. | stage ledger |
| `authority_partition` | Temporary works, environmental, traffic, electrical, structural, and owner approval split. | permit/review matrix |

## Candidate Long-Horizon Products

### SSC-16-LH-01: Construction Environmental Controls, Temporary Traffic, And Monitoring Power Package

This is a construction staging and temporary works work package for construction environmental controls, temporary traffic, and monitoring power. It starts with the staging plan, erosion/sediment control plan, and temporary traffic layout.

The engineer checks sediment/pollutant controls, temporary traffic or device layout, and monitoring power/comms. The output is the construction environmental memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
construction stage and catchment
  -> sediment/pollutant controls
  -> temporary traffic or device layout
  -> monitoring power/comms
  -> construction environmental memo
```

Task-card anchors:

- `sediment-basin-sizing`
- `pollutant-load-estimate`
- `bund-volume-calculation`
- `battery-sizing`
- `road-pdi-calculation`

Source pack:

- staging plan;
- erosion/sediment control plan;
- temporary traffic layout;
- monitoring device schedule;
- temporary power plan.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change staging plan while keeping the downstream sediment/pollutant controls fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make staging plan disagree with erosion/sediment control plan about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in temporary traffic layout only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on construction stage and catchment. The response should show sediment/pollutant controls and temporary traffic or device layout, then record construction environmental memo using the same source values throughout.

### SSC-16-LH-02: Temporary Works Wind And Structural Staging Package

This is a construction staging and temporary works work package for temporary works wind and structural staging. It starts with the staging drawing, temporary structure detail, and wind criteria.

The engineer checks wind speed/pressure case, support or foundation check, and tolerance/installation state. The output is the temporary works memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
temporary structure/stage
  -> wind speed/pressure case
  -> support or foundation check
  -> tolerance/installation state
  -> temporary works memo
```

Task-card anchors:

- `design-wind-speed`
- `design-wind-pressure`
- `load-combinations`
- `construction-tolerance`
- `gravity-base-stability`

Source pack:

- staging drawing;
- temporary structure detail;
- wind criteria;
- support/foundation schedule;
- inspection/tolerance checklist.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change staging drawing while keeping the downstream wind speed/pressure case fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make staging drawing disagree with temporary structure detail about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in wind criteria only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on temporary structure/stage. The response should show wind speed/pressure case and support or foundation check, then record temporary works memo using the same source values throughout.

### SSC-16-LH-03: Dewatering, Settlement, And Temporary Power Package

This is a construction staging and temporary works work package for dewatering, settlement, and temporary power. It starts with the excavation plan, groundwater record, and settlement monitoring table.

The engineer checks groundwater and settlement risk, pump duty/load, and temporary power/back-up. The output is the dewatering memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
excavation/dewatering stage
  -> groundwater and settlement risk
  -> pump duty/load
  -> temporary power/back-up
  -> dewatering memo
```

Task-card anchors:

- `exit-gradient`
- `consolidation-settlement`
- `pump-power-calculation`
- `battery-sizing`
- `voltage-drop`

Source pack:

- excavation plan;
- groundwater record;
- settlement monitoring table;
- pump schedule;
- temporary power layout.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change excavation plan while keeping the downstream groundwater and settlement risk fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make excavation plan disagree with groundwater record about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in settlement monitoring table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on excavation/dewatering stage. The response should show groundwater and settlement risk and pump duty/load, then record dewatering memo using the same source values throughout.

### SSC-16-LH-04: Staged Road/ITS Relocation Package

This is a construction staging and temporary works work package for staged road/ITS relocation. It starts with the temporary traffic plan, device relocation schedule, and signal timing sheet.

The engineer checks temporary signals/VMS/CCTV, communications and power, and pedestrian/vehicle timing. The output is the stage operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
traffic stage and detour
  -> temporary signals/VMS/CCTV
  -> communications and power
  -> pedestrian/vehicle timing
  -> stage operations memo
```

Task-card anchors:

- `pedestrian-clearance-time`
- `vms-legibility-distance`
- `bandwidth-calculation`
- `poe-power-budget`
- `battery-sizing`

Source pack:

- temporary traffic plan;
- device relocation schedule;
- signal timing sheet;
- network topology;
- power schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change temporary traffic plan while keeping the downstream temporary signals/VMS/CCTV fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make temporary traffic plan disagree with device relocation schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in signal timing sheet only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on traffic stage and detour. The response should show temporary signals/VMS/CCTV and communications and power, then record stage operations memo using the same source values throughout.

### SSC-16-LH-05: Sediment Basin And Storm Event Readiness Package

This is a construction staging and temporary works work package for sediment basin and storm event readiness. It starts with the catchment/staging plan, storm event table, and basin detail.

The engineer checks sediment basin volume/outlet, freeboard/overflow consequence, and inspection/maintenance branch. The output is the readiness memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
construction catchment and storm event
  -> sediment basin volume/outlet
  -> freeboard/overflow consequence
  -> inspection/maintenance branch
  -> readiness memo
```

Task-card anchors:

- `sediment-basin-sizing`
- `detention-volume-preliminary`
- `weir-outlet-design`
- `freeboard-calculation`
- `pollutant-load-estimate`

Source pack:

- catchment/staging plan;
- storm event table;
- basin detail;
- inspection checklist;
- discharge criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change catchment/staging plan while keeping the downstream sediment basin volume/outlet fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make catchment/staging plan disagree with storm event table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in basin detail only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on construction catchment and storm event. The response should show sediment basin volume/outlet and freeboard/overflow consequence, then record readiness memo using the same source values throughout.

### SSC-16-LH-06: Temporary Fuel/Chemical Bund And Fire Interface Package

This is a construction staging and temporary works work package for temporary fuel/chemical bund and fire interface. It starts with the storage layout, chemical/fuel inventory, and bund detail.

The engineer checks bund volume and drainage isolation, fire/hazard mode, and monitoring or alarm load. The output is the site safety memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
temporary storage inventory
  -> bund volume and drainage isolation
  -> fire/hazard mode
  -> monitoring or alarm load
  -> site safety memo
```

Task-card anchors:

- `bund-volume-calculation`
- `t-squared-hrr`
- `nac-load-calculation`
- `battery-sizing`
- `visibility-criterion`

Source pack:

- storage layout;
- chemical/fuel inventory;
- bund detail;
- fire/hazard note;
- monitoring load schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change storage layout while keeping the downstream bund volume and drainage isolation fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make storage layout disagree with chemical/fuel inventory about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in bund detail only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on temporary storage inventory. The response should show bund volume and drainage isolation and fire/hazard mode, then record site safety memo using the same source values throughout.

### SSC-16-LH-07: Construction Monitoring Network And Data Continuity Package

This is a construction staging and temporary works work package for construction monitoring network and data continuity. It starts with the monitoring layout, sensor schedule, and network topology.

The engineer checks sensor/device load and data rate, communications path, and battery/solar autonomy. The output is the monitoring continuity memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
monitoring point layout
  -> sensor/device load and data rate
  -> communications path
  -> battery/solar autonomy
  -> monitoring continuity memo
```

Task-card anchors:

- `bandwidth-calculation`
- `rf-link-budget`
- `poe-power-budget`
- `battery-sizing`
- `voltage-drop`

Source pack:

- monitoring layout;
- sensor schedule;
- network topology;
- battery/solar datasheet;
- inspection/reporting rule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change monitoring layout while keeping the downstream sensor/device load and data rate fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make monitoring layout disagree with sensor schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in network topology only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on monitoring point layout. The response should show sensor/device load and data rate and communications path, then record monitoring continuity memo using the same source values throughout.

### SSC-16-LH-08: Staging Review Response And Negative-Case Package

This is a construction staging and temporary works work package for staging review response and negative-case. It starts with the staging plan, control schedule, and device inventory.

The engineer checks review comment or changed stage, affected environmental/traffic/power checks, and repair ledger. The output is the response memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
staging source pack
  -> review comment or changed stage
  -> affected environmental/traffic/power checks
  -> repair ledger
  -> response memo
```

Task-card anchors:

- `construction-tolerance`
- `sediment-basin-sizing`
- `battery-sizing`
- `roadway-spread`
- `design-wind-speed`

Source pack:

- staging plan;
- control schedule;
- device inventory;
- comment register;
- criteria matrix.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change staging plan while keeping the downstream review comment or changed stage fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make staging plan disagree with control schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in device inventory only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on staging design files. The response should show review comment or changed stage and affected environmental/traffic/power checks, then record response memo using the same source values throughout.

## How The Variants Come Together

All `SSC-16` variants should use the same construction staging package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the construction staging package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-16-LH-01` | Construction Environmental Controls, Temporary Traffic, And Monitoring Power Package | `stage_id` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-16-LH-02` | Temporary Works Wind And Structural Staging Package | `temporary_geometry` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-16-LH-03` | Dewatering, Settlement, And Temporary Power Package | `environmental_controls` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-16-LH-04` | Staged Road/ITS Relocation Package | `temporary_traffic_devices` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-16-LH-05` | Sediment Basin And Storm Event Readiness Package | `temporary_power_comms` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-16-LH-06` | Temporary Fuel/Chemical Bund And Fire Interface Package | `weather_event` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-16-LH-07` | Construction Monitoring Network And Data Continuity Package | `handover_state` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-16-LH-08` | Staging Review Response And Negative-Case Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The construction package should keep the same staging plan, temporary works, erosion controls, traffic controls, environmental limits, monitoring, temporary power, and hold points across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

- **Real-world fit:** `SSC-16` maps to construction-phase controls rather than permanent asset design: stormwater pollution prevention, sediment-basin readiness, temporary traffic control, monitoring, temporary power, inspection records, and hold-point response all have to stay aligned to one stage/work area. Useful source routes are the EPA [2022 Construction General Permit](https://www.epa.gov/npdes/2022-construction-general-permit-cgp) and [CGP resources, tools, and templates](https://www.epa.gov/npdes/construction-general-permit-resources-tools-and-templates), FHWA [work zone management](https://ops.fhwa.dot.gov/wz/) and MUTCD [Part 6 temporary traffic control](https://mutcd.fhwa.dot.gov/pdfs/11th_Edition/part6.pdf), and Bentley [SYNCHRO](https://www.bentley.com/software/synchro/) for 4D staging and site-record workflows.
- **Typical practitioner steps:** Define the stage, work area, disturbed catchment, weather/design storm, receiving control, lane closure or shift, monitoring devices, temporary power source, and inspection interval; size/check environmental controls; prepare or review the TTC plan; check data and power continuity; then close the loop through inspections, dewatering/corrective-action records, and construction hold-point comments.
- **Software stack notes:** Practice commonly mixes SWPPP/CGP templates and permit registers, CAD/BIM or traffic-control drawings, 4D planning tools such as SYNCHRO, field inspection/reporting apps, and monitoring telemetry from cameras, turbidity loggers, weather stations, cellular gateways, batteries, and solar skids. The benchmark task should treat those exports as source routes and workflow shapes, not as hidden extra data.
- **Design implications:** A strong task should bind `stage_id`, work-zone ID, erosion-control ID, TTC plan ID, monitoring station ID, power source ID, and inspection record ID before calculations begin. Verifier checks should catch stage drift, wrong basin/device IDs, unsupported storm or taper assumptions, power/data handoff mutation, stale inspection timing, and any claim that a synthetic package is accepted project evidence or full standards compliance.

## Power Playground Skill-Derived Task Candidates

These candidates translate the local `Power-Playground-main` SME review skills into this SSC. They are design-note candidates only; they do not add runnable templates, accepted evidence, or source-pack hardening.

| Candidate Task | Source Skill | Source Pack Shape | What The Check Should Catch |
| --- | --- | --- | --- |
| Can the substation equipment be installed and commissioned without creating a staging hazard? | `substation-safe-design-assessment` | GA object list, equipment dimensions if shown, access openings, replacement path, commissioning zones, cable trenches, temporary works notes, and lifting or vehicle paths. | Installation or commissioning access is blocked, maintainers are forced into unsafe zones, or the task invents access clearances not visible in the source. |
| What temporary safety controls must survive into the construction stage? | `substation-safe-design-assessment` plus `hv-power-system-review` | Staging plan, temporary supply or isolation notes, commissioning sequence, access route, switching state, lockout/interlock assumptions, and verification log. | Temporary operating state, access route, energization boundary, or commissioning hold point changes without being recorded as a source-controlled stage decision. |

## Checks The Template Should Catch

These checks make `SSC-16` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `stage_id` source object or evidence artifact. | `ssc_16_source_identity_mismatch` |
| Scenario drift | One stage uses a different `temporary_geometry` case without a case-selection record. | `ssc_16_scenario_mismatch` |
| Geometry or topology drift | `environmental_controls` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_16_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_16_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_16_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_16_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_16_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_16_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_16_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_16_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-16-LH-01` Construction Environmental Controls, Temporary Traffic, And Monitoring Power Package: start here because it uses the main construction staging package source files and produces a source-pack-sized memo.
2. `SSC-16-LH-02` Temporary Works Wind And Structural Staging Package: add this after the first source pack has stable source files and control values.
3. `SSC-16-LH-03` Dewatering, Settlement, And Temporary Power Package: add this after the first source pack has stable source files and control values.
4. `SSC-16-LH-04` Staged Road/ITS Relocation Package: add this after the first source pack has stable source files and control values.

The next source-pack artifact should be a `construction_source_manifest.yaml` for one product. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-16 product into a source pack.

A first executable-quality source pack for `SSC-16` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `construction_source_manifest.yaml` | source fields such as `stage_id`, `temporary_geometry`, `environmental_controls`, `temporary_traffic_devices`, `temporary_power_comms` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `construction_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `construction_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as construction staging package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
