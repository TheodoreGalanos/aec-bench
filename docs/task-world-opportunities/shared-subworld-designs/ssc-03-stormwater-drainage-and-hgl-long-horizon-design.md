# SSC-03 Stormwater catchment, drainage, and hydraulic grade world Long-Horizon Design

This document treats the stormwater system as one source-controlled drainage package: catchments, rainfall, pits, pipes, storage, outlets, tailwater, and road or site levels have to line up. A useful long-horizon task keeps that drainage basis consistent while moving between hydrology, storage sizing, outlet control, HGL, surface flooding, and authority review.

## Evidence Basis

| Field | Value |
| --- | --- |
| Drainage source state | catchment plan, rainfall/time-series, drainage long section, pits, pipes, detention/outfall structures |
| Memberships | 35 task-card memberships |
| Primary cards | 17 |
| Disciplines | civil, mechanical |
| Score | 27/30 |
| Candidate product | Drainage network plus downstream pump/equipment or road low-point package |
| Main risk | Can collapse into natural civil drainage unless joined to a non-civil shared surface. |

The current card anchors cover catchment, rainfall, storage, outlet, pipe, channel, HGL, and freeboard checks:

| Card | Plain-language role |
| --- | --- |
| `culvert-capacity` | Culvert headwater analysis under inlet and outlet control using HDS-5 methodology. |
| `darcy-weisbach-headloss` | Friction head loss calculation using Darcy-Weisbach equation with Swamee-Jain friction factor. |
| `detention-volume-preliminary` | Preliminary detention volume estimate using simplified triangular hydrograph method. |
| `downpipe-sizing` | Size roof downpipes per AS/NZS 3500.3 using catchment area and rainfall intensity. |
| `flap-gate-headloss` | Flap gate headloss calculation for stormwater outfalls. |
| `gutter-sizing` | Size eaves gutters per AS/NZS 3500.3 using catchment area, rainfall intensity, and gutter grade. |
| `hazen-williams-headloss` | Friction head loss calculation using the Hazen-Williams empirical equation. |
| `hgl-check` | Hydraulic grade line check for a single stormwater pipe reach. |
| `mannings-pipe-capacity` | Flow capacity and velocity in circular pipes using Manning's equation. |
| `open-channel-capacity` | Flow capacity and velocity in trapezoidal/rectangular open channels using Manning's equation. |

## Drainage Data Model

Treat each task as a check against the same drainage network source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-03`, the drainage network source state is:

```text
S_ssc_03 = {
  catchment_partition,
  rainfall_event,
  drainage_network,
  hydraulic_grade_state,
  surface_assets,
  control_energy,
  criteria_targets,
  result_ledger,
}
```

The product combinations below share the same drainage network data. A change to catchment boundary, rainfall event, pipe network, storage curve, outlet, tailwater, or freeboard criterion must carry through each check.

```text
W_ssc03_lh_01 x_S W_ssc03_lh_02
W_ssc03_lh_02 x_S W_ssc03_lh_03
W_ssc03_lh_03 x_S W_ssc03_lh_04
W_ssc03_lh_04 x_S W_ssc03_lh_05
W_ssc03_lh_05 x_S W_ssc03_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_03` | The drainage network source state that all combined checks must agree on. |
| `W_ssc03_lh_01` | The first SSC-03 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same drainage network source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Drainage Source Manifest

Any `SSC-03` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `catchment_partition` | Subcatchments, roofs, roads, imperviousness, and drainage ownership. | catchment plan, GIS export |
| `rainfall_event` | Design storm, temporal pattern, duration, climate factor, and event label. | IDF table, rainfall timeseries |
| `drainage_network` | Pits, pipes, channels, culverts, storage, outlets, and outfalls. | long section, SWMM/HEC model |
| `hydraulic_grade_state` | HGL, surcharge, spread, freeboard, and outlet tailwater. | model output, design table |
| `surface_assets` | Roads, cabinets, entrances, pumps, and other assets affected by water level. | site plan, equipment layout |
| `control_energy` | Pumps, gates, telemetry, controls, or backup supply tied to drainage event. | motor/control schedule |
| `criteria_targets` | Permitted discharge, water-quality, spread, freeboard, or municipal targets. | council criteria, permit note |
| `result_ledger` | Stage outputs, model notes, mismatch disclosures, and failure diagnostics. | design memo, verifier trace |

## Candidate Long-Horizon Products

### SSC-03-LH-01: Detention And Outlet Design-Check Package

This is a stormwater drainage work package for detention and outlet design-check. It starts with the catchment table, IDF/hyetograph or model event, and storage/outlet schedule.

The engineer checks storage volume and outlet sizing, HGL or freeboard check, and report-output trace. The output is the drainage memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
rainfall and catchment basis
  -> storage volume and outlet sizing
  -> HGL or freeboard check
  -> report-output trace
  -> drainage memo
```

Task-card anchors:

- `rational-method`
- `detention-volume-preliminary`
- `orifice-outlet-design`
- `weir-outlet-design`
- `hgl-check`

Source pack:

- catchment table;
- IDF/hyetograph or model event;
- storage/outlet schedule;
- drainage long section;
- SWMM/HEC-style report or task-owned equivalent.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change catchment table while keeping the downstream storage volume and outlet sizing fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make catchment table disagree with IDF/hyetograph or model event about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in storage/outlet schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on rainfall and catchment basis. The response should show storage volume and outlet sizing and HGL or freeboard check, then record drainage memo using the same source values throughout.

### SSC-03-LH-02: Drainage Long Section, HGL, And Road Low-Point Package

This is a stormwater drainage work package for drainage long section, HGL, and road low-point. It starts with the road long section, drainage long section, and pit and pipe schedule.

The engineer checks pipe/pit invert schedule, HGL and roadway spread check, and cabinet or access consequence. The output is the low-point resilience memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
road profile and low point
  -> pipe/pit invert schedule
  -> HGL and roadway spread check
  -> cabinet or access consequence
  -> low-point resilience memo
```

Task-card anchors:

- `pipe-invert-calculation`
- `hgl-check`
- `roadway-spread`
- `pipe-velocity-check`
- `freeboard-calculation`

Source pack:

- road long section;
- drainage long section;
- pit and pipe schedule;
- HGL table;
- roadside equipment or access note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change road long section while keeping the downstream pipe/pit invert schedule fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make road long section disagree with drainage long section about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pit and pipe schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on road profile and low point. The response should show pipe/pit invert schedule and HGL and roadway spread check, then record low-point resilience memo using the same source values throughout.

### SSC-03-LH-03: Stormwater Pump Station Control And Backup-Energy Package

This is a stormwater drainage work package for stormwater pump station control and backup-energy. It starts with the wet-well/pump schedule, inflow or rainfall event table, and rising-main profile.

The engineer checks pump duty and rising-main losses, control/load schedule, and backup autonomy check. The output is the flood-control memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
storage or wet-well inflow case
  -> pump duty and rising-main losses
  -> control/load schedule
  -> backup autonomy check
  -> flood-control memo
```

Task-card anchors:

- `pump-head-calculation`
- `hazen-williams-headloss`
- `pump-power-calculation`
- `battery-sizing`
- `hgl-check`

Source pack:

- wet-well/pump schedule;
- inflow or rainfall event table;
- rising-main profile;
- control panel load schedule;
- battery/generator data sheet.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change wet-well/pump schedule while keeping the downstream pump duty and rising-main losses fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make wet-well/pump schedule disagree with inflow or rainfall event table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in rising-main profile only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on storage or wet-well inflow case. The response should show pump duty and rising-main losses and control/load schedule, then record flood-control memo using the same source values throughout.

### SSC-03-LH-04: Roof Drainage, Gutter/Downpipe, And Facade Interface Package

This is a stormwater drainage work package for roof drainage, gutter/downpipe, and facade interface. It starts with the roof plan and catchment markup, gutter/downpipe schedule, and facade or parapet section.

The engineer checks gutter and downpipe capacity, facade/roof zone and overflow route, and fixing or equipment exposure. The output is the roof drainage memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
roof catchment and rainfall
  -> gutter and downpipe capacity
  -> facade/roof zone and overflow route
  -> fixing or equipment exposure
  -> roof drainage memo
```

Task-card anchors:

- `downpipe-sizing`
- `gutter-sizing`
- `design-wind-pressure`
- `effective-wind-area`
- `freeboard-calculation`

Source pack:

- roof plan and catchment markup;
- gutter/downpipe schedule;
- facade or parapet section;
- rainfall intensity table;
- overflow route sketch.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change roof plan and catchment markup while keeping the downstream gutter and downpipe capacity fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make roof plan and catchment markup disagree with gutter/downpipe schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in facade or parapet section only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on roof catchment and rainfall. The response should show gutter and downpipe capacity and facade/roof zone and overflow route, then record roof drainage memo using the same source values throughout.

### SSC-03-LH-05: Outfall Tailwater, Flap Gate, And Coastal Boundary Package

This is a stormwater drainage work package for outfall tailwater, flap gate, and coastal boundary. It starts with the outfall long section, tide/tailwater table, and flap gate data.

The engineer checks tailwater or tide boundary, flap-gate loss and submergence, and upstream HGL consequence. The output is the outfall design note. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
drainage network outfall
  -> tailwater or tide boundary
  -> flap-gate loss and submergence
  -> upstream HGL consequence
  -> outfall design note
```

Task-card anchors:

- `outfall-submergence-check`
- `flap-gate-headloss`
- `hgl-check`
- `freeboard-calculation`
- `tidal-prism`

Source pack:

- outfall long section;
- tide/tailwater table;
- flap gate data;
- upstream pipe network schedule;
- coastal/freeboard criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change outfall long section while keeping the downstream tailwater or tide boundary fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make outfall long section disagree with tide/tailwater table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in flap gate data only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on drainage network outfall. The response should show tailwater or tide boundary and flap-gate loss and submergence, then record outfall design note using the same source values throughout.

### SSC-03-LH-06: Water Quality, Pollutant Load, And Construction Sediment Package

This is a stormwater drainage work package for water quality, pollutant load, and construction sediment. It starts with the construction staging plan, land-use/catchment table, and pollutant concentration basis.

The engineer checks pollutant load estimate, sediment basin sizing, and temporary discharge route. The output is the environmental control memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
land use and construction stage
  -> pollutant load estimate
  -> sediment basin sizing
  -> temporary discharge route
  -> environmental control memo
```

Task-card anchors:

- `pollutant-load-estimate`
- `sediment-basin-sizing`
- `detention-volume-preliminary`
- `weir-outlet-design`
- `open-channel-capacity`

Source pack:

- construction staging plan;
- land-use/catchment table;
- pollutant concentration basis;
- sediment basin sketch;
- discharge or receiving-water criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change construction staging plan while keeping the downstream pollutant load estimate fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make construction staging plan disagree with land-use/catchment table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pollutant concentration basis only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on land use and construction stage. The response should show pollutant load estimate and sediment basin sizing, then record environmental control memo using the same source values throughout.

### SSC-03-LH-07: Sewer/Storm Pipe Gradient And Capacity Repair Package

This is a stormwater drainage work package for sewer/storm pipe gradient and capacity repair. It starts with the pipe schedule, invert table, and long section.

The engineer checks slope and invert consistency, capacity and velocity check, and repair or redesign option. The output is the network correction memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
pipe network schedule
  -> slope and invert consistency
  -> capacity and velocity check
  -> repair or redesign option
  -> network correction memo
```

Task-card anchors:

- `sewer-pipe-sizing`
- `sewer-slope-check`
- `mannings-pipe-capacity`
- `pipe-invert-calculation`
- `velocity-check`

Source pack:

- pipe schedule;
- invert table;
- long section;
- capacity criteria;
- change ledger.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change pipe schedule while keeping the downstream slope and invert consistency fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make pipe schedule disagree with invert table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in long section only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on pipe network schedule. The response should show slope and invert consistency and capacity and velocity check, then record network correction memo using the same source values throughout.

### SSC-03-LH-08: SWMM/HEC-Style Report Output And Source-Policy Package

This is a stormwater drainage work package for SWMM/HEC-style report output and source-policy. It starts with the model input file, manual or report PDF, and result table.

The engineer checks static parse of objects/options, report-output or manual target check, and negative cases for output claims. The output is the source-policy memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
model files and source hashes
  -> static parse of objects/options
  -> report-output or manual target check
  -> negative cases for output claims
  -> source-policy memo
```

Task-card anchors:

- `detention-volume-preliminary`
- `hgl-check`
- `orifice-outlet-design`
- `weir-outlet-design`
- `freeboard-calculation`

Source pack:

- model input file;
- manual or report PDF;
- result table;
- hash/source manifest;
- verification case matrix.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change model input file while keeping the downstream static parse of objects/options fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make model input file disagree with manual or report PDF about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in result table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on model files and source hashes. The response should show static parse of objects/options and report-output or manual target check, then record source-policy memo using the same source values throughout.

## How The Variants Come Together

All `SSC-03` variants should use the same drainage network workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the drainage network package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-03-LH-01` | Detention And Outlet Design-Check Package | `catchment_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-03-LH-02` | Drainage Long Section, HGL, And Road Low-Point Package | `rainfall_event` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-03-LH-03` | Stormwater Pump Station Control And Backup-Energy Package | `drainage_network` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-03-LH-04` | Roof Drainage, Gutter/Downpipe, And Facade Interface Package | `hydraulic_grade_state` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-03-LH-05` | Outfall Tailwater, Flap Gate, And Coastal Boundary Package | `surface_assets` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-03-LH-06` | Water Quality, Pollutant Load, And Construction Sediment Package | `control_energy` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-03-LH-07` | Sewer/Storm Pipe Gradient And Capacity Repair Package | `criteria_targets` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-03-LH-08` | SWMM/HEC-Style Report Output And Source-Policy Package | `result_ledger` | Keeps this control point consistent across the source pack, calculations, and memo. |

The drainage package should keep the same catchment plan, rainfall event, drainage network, storage, outlets, tailwater, HGL, and surface assets across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when treated as a stormwater design package that moves from catchment/rainfall/loss assumptions into a model network, storage/outlet controls, HGL/spread/freeboard checks, water-quality or LID controls, and report outputs.
- Not every drainage task needs a long multi-stage package. The long-horizon behaviour appears when one catchment/event/model output affects a road low point, pump station, roof/facade interface, coastal tailwater/outfall, construction sediment case, or review response.
- The current products make sense if the source pack requires event/model version control and does not let manual summary values drift away from model files or report outputs.

Typical practitioner steps:

1. Define catchments, rainfall event or time series, loss method, imperviousness, surface levels, drainage network, storage, and outlet/tailwater boundary.
2. Run hydrologic and hydraulic modelling, then inspect continuity, peak flows, HGL, surcharge, storage levels, and outlet performance.
3. Check road spread, freeboard, detention release, pump controls, outfall tailwater, water-quality controls, or construction sediment case from the same model scenario.
4. Issue a report or calculation memo that ties catchment assumptions, model version, report tables, design targets, and changed drawings together.

Software stack notes:

- [EPA SWMM](https://www.epa.gov/water-research/storm-water-management-model-swmm) is a realistic modelling anchor for drainage networks, storage/treatment units, weirs, orifices, pumps, dynamic-wave routing, controls, maps, time series, tables, and profile plots.
- [HEC-HMS](https://www.hec.usace.army.mil/software/hec-hms/) is a realistic watershed hydrology anchor for infiltration, unit hydrographs, routing, continuous simulation, uncertainty, urban drainage, and flow forecasting studies.
- [HEC-RAS](https://www.hec.usace.army.mil/software/hec-ras/) is a realistic hydraulic/flood anchor for 1D/2D unsteady flow, sediment/mobile-bed, stormwater pipe-network modelling, and water-quality/temperature cases.
- [EPA National Stormwater Calculator](https://www.epa.gov/water-research/national-stormwater-calculator) is a realistic screening/LID anchor for small-to-medium sites, runoff capture, green infrastructure controls, and planning-level cost/performance comparisons.

Design implications:

- Add `model_version_register`, `rainfall_event_register`, `outlet_control_schedule`, and `report_output_index` fields before hardening `SSC-03-LH-01`.
- Preserve model-file and report-output traceability; manual target values should not override model outputs unless the memo records the source conflict.
- Negative cases should include wrong tailwater boundary, manual/model mismatch, missing continuity/report-output evidence, and outlet-control rows not matching the model file.

## Checks The Template Should Catch

These checks make `SSC-03` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `catchment_partition` source object or evidence artifact. | `ssc_03_source_identity_mismatch` |
| Scenario drift | One stage uses a different `rainfall_event` case without a case-selection record. | `ssc_03_scenario_mismatch` |
| Geometry or topology drift | `drainage_network` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_03_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `result_ledger` are treated as interchangeable. | `ssc_03_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_03_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_03_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_03_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_03_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_03_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_03_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-03-LH-01` Detention And Outlet Design-Check Package: start here because it uses the main drainage network source files and produces a source-pack-sized memo.
2. `SSC-03-LH-02` Drainage Long Section, HGL, And Road Low-Point Package: add this after the first source pack has stable source files and control values.
3. `SSC-03-LH-03` Stormwater Pump Station Control And Backup-Energy Package: add this after the first source pack has stable source files and control values.
4. `SSC-03-LH-04` Roof Drainage, Gutter/Downpipe, And Facade Interface Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `drainage_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-03 product into a source pack.

A first executable-quality source pack for `SSC-03` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `drainage_source_manifest.yaml` | source fields such as `catchment_partition`, `rainfall_event`, `drainage_network`, `hydraulic_grade_state`, `surface_assets` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `drainage_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `drainage_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as drainage network product notes, while the source-pack build notes should be used only to guide later fixture packaging.
