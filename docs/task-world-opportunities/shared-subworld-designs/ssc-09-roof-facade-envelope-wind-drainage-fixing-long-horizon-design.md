# SSC-09 Roof/facade/envelope wind, drainage, and fixing world Long-Horizon Design

This document treats the roof and facade as one source-controlled envelope package: geometry, wind zones, panel or roof areas, drainage, brackets, anchors, tolerances, and access assumptions have to line up. A useful long-horizon task keeps that envelope basis consistent while moving between wind pressure, drainage, PV support, brackets, anchors, fixings, and maintenance checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Envelope source state | roof/facade geometry, pressure zones, PV/racking layout, gutters/downpipes, brackets/tolerances |
| Memberships | 16 task-card memberships |
| Primary cards | 2 |
| Disciplines | civil, electrical, structural |
| Score | 26/30 |
| Candidate product | Roof/facade/PV wind, drainage, access tolerance, and fixing package |
| Main risk | Needs geometry ownership so wind, drainage, and fixing zones do not drift. |

The current card anchors cover wind, facade, roof drainage, PV support, load combination, bracket, anchor, and fixing checks:

| Card | Plain-language role |
| --- | --- |
| `design-wind-pressure` | Calculates design wind pressure from wind speed and aerodynamic factors per AS/NZS 1170.2. |
| `design-wind-speed` | Site wind speed V_sit,beta from regional speed and multipliers per AS/NZS 1170.2. |
| `downpipe-sizing` | Size roof downpipes per AS/NZS 3500.3 using catchment area and rainfall intensity. |
| `gutter-sizing` | Size eaves gutters per AS/NZS 3500.3 using catchment area, rainfall intensity, and gutter grade. |
| `roadway-spread` | Roadway gutter spread width and curb depth from HEC-22 Manning's equation for triangular cross-sections. |
| `sls-load-combinations` | Generate and check serviceability limit state load combinations per AS/NZS 1170.0 Table 4.1. |
| `solar-array-wind-load` | Wind loads on ground-mounted solar PV arrays including uplift, downforce, and drag. |
| `uls-load-combinations` | Generate and check ultimate limit state load combinations per AS/NZS 1170.0 Table 4.1. |
| `ice-load-calculation` | Calculates ice and wind loading on an overhead conductor. |
| `wind-load-conductor` | Calculates wind load on an overhead conductor span. |

## Envelope And Roof Data Model

Treat each task as a check against the same roof and facade package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-09`, the roof and facade package source state is:

```text
S_ssc_09 = {
  envelope_geometry,
  pressure_or_wind_zones,
  drainage_catchments,
  support_fixing_schedule,
  pv_or_roof_equipment,
  tolerance_setout,
  load_combinations,
  authority_partition,
}
```

The product combinations below share the same roof and facade package data. A change to facade elevation, roof geometry, wind zone, panel weight, gutter, downpipe, bracket, anchor, or tolerance must carry through each check.

```text
W_ssc09_lh_01 x_S W_ssc09_lh_02
W_ssc09_lh_02 x_S W_ssc09_lh_03
W_ssc09_lh_03 x_S W_ssc09_lh_04
W_ssc09_lh_04 x_S W_ssc09_lh_05
W_ssc09_lh_05 x_S W_ssc09_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_09` | The roof and facade package source state that all combined checks must agree on. |
| `W_ssc09_lh_01` | The first SSC-09 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same roof and facade package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Envelope Source Manifest

Any `SSC-09` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `envelope_geometry` | Roof/facade extents, elevations, zones, openings, parapets, and access areas. | roof/facade drawings |
| `pressure_or_wind_zones` | Wind region, pressure zones, height, terrain, internal pressure, and zone IDs. | wind calculation |
| `drainage_catchments` | Gutter/downpipe/roof catchment areas and rainfall basis. | roof drainage plan |
| `support_fixing_schedule` | Brackets, rails, anchors, fasteners, substrates, and capacities. | submittal/calculation |
| `pv_or_roof_equipment` | PV arrays, plant, maintenance zones, cable routes, and loads. | PV/plant layout |
| `tolerance_setout` | Datum, support spacing, movement joints, shim, tolerance, and fixed/sliding support rules. | shop drawings |
| `load_combinations` | ULS/SLS, dead, wind, seismic, maintenance, and thermal actions. | structural basis |
| `authority_partition` | Architectural, structural, facade, drainage, electrical, and fire/access criteria split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-09-LH-01: Facade Wind, Bracket, Anchor, And Tolerance Package

This is a roof and facade envelope work package for facade wind, bracket, anchor, and tolerance. It starts with the wind criteria, facade elevation, and pressure zone schedule.

The engineer checks panel tributary area, bracket/anchor demand and capacity, and tolerance or setout check. The output is the facade fixing memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
wind criteria and facade zone
  -> panel tributary area
  -> bracket/anchor demand and capacity
  -> tolerance or setout check
  -> facade fixing memo
```

Task-card anchors:

- `design-wind-speed`
- `design-wind-pressure`
- `effective-wind-area`
- `bracket-load-calc`
- `construction-tolerance`

Source pack:

- wind criteria;
- facade elevation;
- pressure zone schedule;
- bracket/anchor capacity table;
- tolerance or installation detail.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change wind criteria while keeping the downstream panel tributary area fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make wind criteria disagree with facade elevation about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pressure zone schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on wind criteria and facade zone. The response should show panel tributary area and bracket/anchor demand and capacity, then record facade fixing memo using the same source values throughout.

### SSC-09-LH-02: Roof Drainage, PV Layout, And Wind Uplift Package

This is a roof and facade envelope work package for roof drainage, PV layout, and wind uplift. It starts with the roof plan, PV/rack layout, and gutter/downpipe schedule.

The engineer checks PV/racking layout, wind pressure/uplift case, and fixing and overflow consequence. The output is the roof package memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
roof catchment and drainage layout
  -> PV/racking layout
  -> wind pressure/uplift case
  -> fixing and overflow consequence
  -> roof package memo
```

Task-card anchors:

- `downpipe-sizing`
- `gutter-sizing`
- `solar-array-wind-load`
- `design-wind-pressure`
- `sls-load-combinations`

Source pack:

- roof plan;
- PV/rack layout;
- gutter/downpipe schedule;
- wind pressure zones;
- fixing capacity table.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change roof plan while keeping the downstream PV/racking layout fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make roof plan disagree with PV/rack layout about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in gutter/downpipe schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on roof catchment and drainage layout. The response should show PV/racking layout and wind pressure/uplift case, then record roof package memo using the same source values throughout.

### SSC-09-LH-03: Envelope Access, Maintenance, And Safety Package

This is a roof and facade envelope work package for envelope access, maintenance, and safety. It starts with the access plan, facade/roof detail, and load/tolerance schedule.

The engineer checks maintenance load or tolerance case, fall/weather exposure, and fixing/access support check. The output is the maintenance safety memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
facade/roof access route
  -> maintenance load or tolerance case
  -> fall/weather exposure
  -> fixing/access support check
  -> maintenance safety memo
```

Task-card anchors:

- `construction-tolerance`
- `bracket-load-calc`
- `load-combinations`
- `wind-load-conductor`
- `roadway-spread`

Source pack:

- access plan;
- facade/roof detail;
- load/tolerance schedule;
- weather criterion;
- maintenance operations note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change access plan while keeping the downstream maintenance load or tolerance case fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make access plan disagree with facade/roof detail about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in load/tolerance schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on facade/roof access route. The response should show maintenance load or tolerance case and fall/weather exposure, then record maintenance safety memo using the same source values throughout.

### SSC-09-LH-04: Canopy, Signage, Lighting, And Envelope Fixing Package

This is a roof and facade envelope work package for canopy, signage, lighting, and envelope fixing. It starts with the canopy/signage elevation, wind criteria, and lighting/device schedule.

The engineer checks wind and dead load, lighting/device load, and bracket/anchor/fixing check. The output is the integrated facade memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
canopy/signage geometry
  -> wind and dead load
  -> lighting/device load
  -> bracket/anchor/fixing check
  -> integrated facade memo
```

Task-card anchors:

- `design-wind-pressure`
- `bracket-load-calc`
- `voltage-drop`
- `poe-power-budget`
- `load-combinations`

Source pack:

- canopy/signage elevation;
- wind criteria;
- lighting/device schedule;
- anchor capacity table;
- structural detail.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change canopy/signage elevation while keeping the downstream wind and dead load fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make canopy/signage elevation disagree with wind criteria about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in lighting/device schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on canopy/signage geometry. The response should show wind and dead load and lighting/device load, then record integrated facade memo using the same source values throughout.

### SSC-09-LH-05: Rainscreen Drainage, Cavity, And Fire/Material Review Package

This is a roof and facade envelope work package for rainscreen drainage, cavity, and fire/material review. It starts with the rainscreen detail, product datasheets, and cavity/fire-stop schedule.

The engineer checks drainage/ventilation cavity state, material/product class, and fixing and fire-stopping review. The output is the envelope review memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
rainscreen build-up
  -> drainage/ventilation cavity state
  -> material/product class
  -> fixing and fire-stopping review
  -> envelope review memo
```

Task-card anchors:

- `bracket-load-calc`
- `carbon-equivalent-calc`
- `downpipe-sizing`
- `steel-critical-temp`
- `construction-tolerance`

Source pack:

- rainscreen detail;
- product datasheets;
- cavity/fire-stop schedule;
- fixing schedule;
- review/authority criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change rainscreen detail while keeping the downstream drainage/ventilation cavity state fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make rainscreen detail disagree with product datasheets about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in cavity/fire-stop schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on rainscreen build-up. The response should show drainage/ventilation cavity state and material/product class, then record envelope review memo using the same source values throughout.

### SSC-09-LH-06: Facade Zone Difference And Re-Entrant Geometry Package

This is a roof and facade envelope work package for facade zone difference and re-entrant geometry. It starts with the baseline and variant elevation, zone schedule, and support point table.

The engineer checks changed opening or re-entrant corner, pressure zone reassignment, and bracket/anchor utilization change. The output is the variant comparison memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
baseline elevation
  -> changed opening or re-entrant corner
  -> pressure zone reassignment
  -> bracket/anchor utilization change
  -> variant comparison memo
```

Task-card anchors:

- `effective-wind-area`
- `design-wind-pressure`
- `bracket-load-calc`
- `load-combinations`
- `construction-tolerance`

Source pack:

- baseline and variant elevation;
- zone schedule;
- support point table;
- capacity table;
- variant matrix.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change baseline and variant elevation while keeping the downstream changed opening or re-entrant corner fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make baseline and variant elevation disagree with zone schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in support point table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on baseline elevation. The response should show changed opening or re-entrant corner and pressure zone reassignment, then record variant comparison memo using the same source values throughout.

### SSC-09-LH-07: Roof/Fall/Drainage Conflict And Repair Package

This is a roof and facade envelope work package for roof/fall/drainage conflict and repair. It starts with the roof fall plan, gutter schedule, and downpipe schedule.

The engineer checks gutter/downpipe capacity, overflow route, and facade or equipment exposure. The output is the repair response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
roof slope/fall source
  -> gutter/downpipe capacity
  -> overflow route
  -> facade or equipment exposure
  -> repair response
```

Task-card anchors:

- `gutter-sizing`
- `downpipe-sizing`
- `roadway-spread`
- `freeboard-calculation`
- `construction-tolerance`

Source pack:

- roof fall plan;
- gutter schedule;
- downpipe schedule;
- overflow sketch;
- facade/equipment exposure note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change roof fall plan while keeping the downstream gutter/downpipe capacity fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make roof fall plan disagree with gutter schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in downpipe schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on roof slope/fall source. The response should show gutter/downpipe capacity and overflow route, then record repair response using the same source values throughout.

### SSC-09-LH-08: Facade Submittal Review And Source-Policy Package

This is a roof and facade envelope work package for facade submittal review and source-policy. It starts with the source index, redrawn elevation, and calculator/report output.

The engineer checks calculator/manufacturer output, redrawn elevation boundary, and utilization evidence. The output is the submittal response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
project source index
  -> calculator/manufacturer output
  -> redrawn elevation boundary
  -> utilization evidence
  -> submittal response
```

Task-card anchors:

- `bracket-load-calc`
- `effective-wind-area`
- `carbon-equivalent-calc`
- `load-combinations`
- `construction-tolerance`

Source pack:

- source index;
- redrawn elevation;
- calculator/report output;
- material schedule;
- review comments.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change source index while keeping the downstream calculator/manufacturer output fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make source index disagree with redrawn elevation about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in calculator/report output only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on project source index. The response should show calculator/manufacturer output and redrawn elevation boundary, then record submittal response using the same source values throughout.

## How The Variants Come Together

All `SSC-09` variants should use the same roof and facade package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the roof and facade package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-09-LH-01` | Facade Wind, Bracket, Anchor, And Tolerance Package | `envelope_geometry` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-09-LH-02` | Roof Drainage, PV Layout, And Wind Uplift Package | `pressure_or_wind_zones` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-09-LH-03` | Envelope Access, Maintenance, And Safety Package | `drainage_catchments` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-09-LH-04` | Canopy, Signage, Lighting, And Envelope Fixing Package | `support_fixing_schedule` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-09-LH-05` | Rainscreen Drainage, Cavity, And Fire/Material Review Package | `pv_or_roof_equipment` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-09-LH-06` | Facade Zone Difference And Re-Entrant Geometry Package | `tolerance_setout` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-09-LH-07` | Roof/Fall/Drainage Conflict And Repair Package | `load_combinations` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-09-LH-08` | Facade Submittal Review And Source-Policy Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The envelope package should keep the same roof and facade geometry, wind zones, panel areas, drainage assets, brackets, anchors, tolerances, and access assumptions across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when roof and facade work is treated as one weather-exposed envelope package with shared geometry, pressure zones, drainage catchments, panel weights, support brackets, anchors, tolerances, and product certificates. Real practice fails quickly when the wind, drainage, and fixing teams each redraw the elevation or roof plan independently.
- The facade package is strongest where the model must carry a pressure-zone/elevation object through bracket spacing, rail or support selection, anchor/substrate checks, thermal or movement allowances, and submittal review comments.
- The roof-drainage and PV variants are plausible only when catchment area, fall direction, overflow path, wind uplift, equipment layout, and penetration/support details are source-owned by the same packet.

Typical practitioner steps:

1. Register the roof/facade geometry, elevations, pressure zones, catchments, cladding or roof-system build-up, equipment locations, substrate, tolerances, and authority or manufacturer criteria.
2. Derive local wind actions, tributary areas, drainage flows, bracket/rail or fastener spacing, anchor reactions, movement allowances, and maintenance/access constraints.
3. Check the selected system against product limits, wind and gravity actions, drainage capacity, support layout, anchor geometry, and installation tolerance.
4. Issue a memo or submittal response that ties drawings, zones, product selections, calculations, capacity excerpts, and unresolved source limits together.

Software stack notes:

- [ASCE Hazard Tool](https://ascehazardtool.org/) is a realistic hazard-lookup anchor for US wind parameters before the package turns location, exposure, height, and risk category into pressure zones.
- [SFS/NVELOPE Project Builder](https://www.sfs.com/uk-en/products/architectural-envelope/nvelope-rainscreen-systems/project-builder) is a realistic rainscreen-support workflow anchor for project-specific support spacing, bracket/rail quantities, static-calculation outputs, and drawing-overlay semantics.
- [Hilti PROFIS Engineering](https://www.hilti.com/content/hilti/W1/US/en/engineering/design-center/profis-engineering.html) is a realistic anchor/baseplate design anchor when facade or canopy reactions must become tension, shear, edge-distance, embedment, and utilization checks.
- [Cascadia Clip](https://www.cascadiawindows.com/cascadia-clip/) is a realistic North American cladding-attachment route for clip/rail spacing, thermal-break constraints, fastening, and product-report evidence.

Design implications:

- Add `envelope_geometry_register`, `pressure_zone_schedule`, `drainage_catchment_schedule`, `support_fixing_schedule`, and `product_capacity_excerpt` fields before hardening `SSC-09-LH-01`.
- Require drawing IDs, zone IDs, panel/catchment IDs, bracket/support IDs, and anchor/substrate IDs to survive into the memo and review response.
- Negative cases should include a wind zone applied to the wrong facade strip, a roof-drainage catchment changed after PV layout, and an anchor check that loses edge-distance or substrate evidence.

## Checks The Template Should Catch

These checks make `SSC-09` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `envelope_geometry` source object or evidence artifact. | `ssc_09_source_identity_mismatch` |
| Scenario drift | One stage uses a different `pressure_or_wind_zones` case without a case-selection record. | `ssc_09_scenario_mismatch` |
| Geometry or topology drift | `drainage_catchments` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_09_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_09_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_09_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_09_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_09_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_09_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_09_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_09_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-09-LH-01` Facade Wind, Bracket, Anchor, And Tolerance Package: start here because it uses the main roof and facade package source files and produces a source-pack-sized memo.
2. `SSC-09-LH-02` Roof Drainage, PV Layout, And Wind Uplift Package: add this after the first source pack has stable source files and control values.
3. `SSC-09-LH-03` Envelope Access, Maintenance, And Safety Package: add this after the first source pack has stable source files and control values.
4. `SSC-09-LH-04` Canopy, Signage, Lighting, And Envelope Fixing Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `envelope_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-09 product into a source pack.

A first executable-quality source pack for `SSC-09` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `envelope_source_manifest.yaml` | source fields such as `envelope_geometry`, `pressure_or_wind_zones`, `drainage_catchments`, `support_fixing_schedule`, `pv_or_roof_equipment` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `envelope_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `envelope_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as roof and facade package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
