# SSC-04 Coastal, flood, wave, and marine boundary world Long-Horizon Design

This document treats the coastal boundary as one source-controlled design package: datum, tide, sea-level allowance, wave climate, shoreline profile, outfall levels, and asset elevations have to line up. A useful long-horizon task keeps that marine basis consistent while moving between flood level, wave, outfall, pump, structural, and electrical elevation checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Coastal source state | coastal profile, tide/SLR table, wave climate, runup/freeboard, outfall/asset level |
| Memberships | 13 task-card memberships |
| Primary cards | 9 |
| Disciplines | civil, mechanical, structural |
| Score | 25/30 |
| Candidate product | Coastal flood/outfall/pump/electrical elevation package |
| Main risk | Datum and planning-horizon control must be explicit before joining assets. |

The current card anchors cover tide, sea-level rise, wave, runup, freeboard, armor, outfall, and coastal-asset checks:

| Card | Plain-language role |
| --- | --- |
| `cerc-longshore-transport` | Longshore sediment transport rate using the CERC formula Q_l = K * (E*Cg)_b * sin(2*alpha_b) / (2 * (rho_s - rho_w) * g * (1 - p)). |
| `freeboard-calculation` | Freeboard calculation for coastal/flood structures: total freeboard = wave_allowance + slr_allowance + construction_tolerance + safety_margin (NZS 4404 / MfE Guidance). |
| `hudson-armor-sizing` | Armor stone sizing using Hudson's equation W = rho_r * H^3 / (KD * (Sr-1)^3 * cot(alpha)). |
| `linear-wave-theory` | Linear (Airy) wave theory: wavelength, celerity, and group velocity via dispersion relation (USACE CEM). |
| `outfall-submergence-check` | Outfall submergence analysis: fraction of tidal cycle an outfall invert is submerged under present and future sea levels. |
| `tidal-prism` | Tidal prism and mean inlet velocity for a coastal basin. |
| `wave-breaking` | Wave breaking criteria using depth-limited breaking height, Iribarren number, and breaker type classification (USACE CEM). |
| `wave-runup` | 2% exceedance wave runup on coastal structures using EurOtop (2018) TAW formula. |
| `wave-shoaling` | Wave shoaling and refraction using Fenton & McKee (1990) explicit wavelength approximation and Snell's law (USACE CEM). |
| `slr-calculation` | Secondary clarifier solids loading rate calculation. |

## Coastal And Marine Data Model

Treat each task as a check against the same coastal and marine boundary source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-04`, the coastal and marine boundary source state is:

```text
S_ssc_04 = {
  datum_frame,
  planning_horizon,
  water_level_series,
  coastal_profile,
  marine_actions,
  asset_elevations,
  operating_event,
  authority_partition,
}
```

The product combinations below share the same coastal and marine boundary data. A change to datum, tide level, sea-level allowance, wave case, shoreline profile, outfall level, or asset elevation must carry through each check.

```text
W_ssc04_lh_01 x_S W_ssc04_lh_02
W_ssc04_lh_02 x_S W_ssc04_lh_03
W_ssc04_lh_03 x_S W_ssc04_lh_04
W_ssc04_lh_04 x_S W_ssc04_lh_05
W_ssc04_lh_05 x_S W_ssc04_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_04` | The coastal and marine boundary source state that all combined checks must agree on. |
| `W_ssc04_lh_01` | The first SSC-04 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same coastal and marine boundary source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Coastal Source Manifest

Any `SSC-04` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `datum_frame` | Vertical datum for tide, SLR, asset levels, outfalls, and equipment. | survey control, tide table |
| `planning_horizon` | Current, future, climate, or SLR year and allowance. | planning criteria |
| `water_level_series` | Tide, surge, wave, runup, tailwater, and freeboard levels. | coastal study |
| `coastal_profile` | Beach, seawall, outfall, pump station, wharf, or asset section. | profile/section drawing |
| `marine_actions` | Wave, berthing, fender, armor, or outfall hydraulic actions. | marine calculation |
| `asset_elevations` | Pumps, switchboards, roads, decks, outfalls, and controls. | site/equipment schedule |
| `operating_event` | Storm tide, wave climate, closure, outage, or marine impact case. | operations note |
| `authority_partition` | Coastal, drainage, structural, electrical, and port/owner criteria split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-04-LH-01: Coastal Flood, Outfall, Pump, And Electrical Elevation Package

This is a coastal, flood, and marine boundary work package for coastal flood, outfall, pump, and electrical elevation. It starts with the tide/SLR/storm level table, site section and datum note, and outfall or pump schedule.

The engineer checks outfall or pump hydraulic state, asset/equipment elevation check, and backup or shutdown consequence. The output is the flood resilience memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
coastal level and planning horizon
  -> outfall or pump hydraulic state
  -> asset/equipment elevation check
  -> backup or shutdown consequence
  -> flood resilience memo
```

Task-card anchors:

- `slr-calculation`
- `outfall-submergence-check`
- `pump-head-calculation`
- `freeboard-calculation`
- `voltage-drop`

Source pack:

- tide/SLR/storm level table;
- site section and datum note;
- outfall or pump schedule;
- electrical/equipment elevation layout;
- coastal planning criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change tide/SLR/storm level table while keeping the downstream outfall or pump hydraulic state fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make tide/SLR/storm level table disagree with site section and datum note about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in outfall or pump schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on coastal level and planning horizon. The response should show outfall or pump hydraulic state and asset/equipment elevation check, then record flood resilience memo using the same source values throughout.

### SSC-04-LH-02: Wave Runup, Freeboard, And Asset Protection Package

This is a coastal, flood, and marine boundary work package for wave runup, freeboard, and asset protection. It starts with the wave climate table, shore profile, and asset level table.

The engineer checks shoaling/breaking/runup calculation, freeboard or overtopping consequence, and armor or barrier check. The output is the asset protection memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
wave climate and shore profile
  -> shoaling/breaking/runup calculation
  -> freeboard or overtopping consequence
  -> armor or barrier check
  -> asset protection memo
```

Task-card anchors:

- `linear-wave-theory`
- `wave-shoaling`
- `wave-breaking`
- `wave-runup`
- `freeboard-calculation`

Source pack:

- wave climate table;
- shore profile;
- asset level table;
- armor/barrier schedule;
- design horizon criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change wave climate table while keeping the downstream shoaling/breaking/runup calculation fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make wave climate table disagree with shore profile about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in asset level table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on wave climate and shore profile. The response should show shoaling/breaking/runup calculation and freeboard or overtopping consequence, then record asset protection memo using the same source values throughout.

### SSC-04-LH-03: Marine Berthing, Fender, And Storm Operations Package

This is a coastal, flood, and marine boundary work package for marine berthing, fender, and storm operations. It starts with the vessel data sheet, berth layout, and fender or mooring schedule.

The engineer checks berthing/fender energy check, mooring or structural capacity, and storm or tide operating limit. The output is the marine operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
vessel and berth scenario
  -> berthing/fender energy check
  -> mooring or structural capacity
  -> storm or tide operating limit
  -> marine operations memo
```

Task-card anchors:

- `berthing-energy-calc`
- `fender-energy-check`
- `mooring-line-capacity`
- `tidal-prism`
- `wind-load-conductor`

Source pack:

- vessel data sheet;
- berth layout;
- fender or mooring schedule;
- tide/weather table;
- port operations rule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change vessel data sheet while keeping the downstream berthing/fender energy check fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make vessel data sheet disagree with berth layout about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in fender or mooring schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on vessel and berth scenario. The response should show berthing/fender energy check and mooring or structural capacity, then record marine operations memo using the same source values throughout.

### SSC-04-LH-04: Flap Gate, Tide, And Drainage Resilience Package

This is a coastal, flood, and marine boundary work package for flap gate, tide, and drainage resilience. It starts with the outfall section, flap gate data, and tailwater/tide table.

The engineer checks tide/tailwater boundary, headloss and upstream HGL, and storm outage or pump consequence. The output is the resilience note. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
drainage outfall and flap gate
  -> tide/tailwater boundary
  -> headloss and upstream HGL
  -> storm outage or pump consequence
  -> resilience note
```

Task-card anchors:

- `flap-gate-headloss`
- `outfall-submergence-check`
- `hgl-check`
- `pump-power-calculation`
- `battery-sizing`

Source pack:

- outfall section;
- flap gate data;
- tailwater/tide table;
- upstream drainage schedule;
- pump/control load note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change outfall section while keeping the downstream tide/tailwater boundary fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make outfall section disagree with flap gate data about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in tailwater/tide table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on drainage outfall and flap gate. The response should show tide/tailwater boundary and headloss and upstream HGL, then record resilience note using the same source values throughout.

### SSC-04-LH-05: Coastal Erosion, Longshore Transport, And Temporary Works Package

This is a coastal, flood, and marine boundary work package for coastal erosion, longshore transport, and temporary works. It starts with the beach profile, sediment grading table, and wave climate.

The engineer checks longshore transport estimate, temporary protection or staging, and construction discharge and monitoring. The output is the erosion-control memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
shoreline/sediment basis
  -> longshore transport estimate
  -> temporary protection or staging
  -> construction discharge and monitoring
  -> erosion-control memo
```

Task-card anchors:

- `cerc-longshore-transport`
- `sediment-basin-sizing`
- `wave-shoaling`
- `freeboard-calculation`
- `construction-tolerance`

Source pack:

- beach profile;
- sediment grading table;
- wave climate;
- temporary works plan;
- monitoring/permit criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change beach profile while keeping the downstream longshore transport estimate fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make beach profile disagree with sediment grading table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in wave climate only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on shoreline/sediment basis. The response should show longshore transport estimate and temporary protection or staging, then record erosion-control memo using the same source values throughout.

### SSC-04-LH-06: Sea-Level-Rise Scenario And Asset-Level Review Package

This is a coastal, flood, and marine boundary work package for sea-level-rise scenario and asset-level review. It starts with the asset register with levels, SLR scenario table, and storm tide table.

The engineer checks SLR and storm-tide scenarios, freeboard and service-level check, and adaptation design decision. The output is the review response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
baseline asset level
  -> SLR and storm-tide scenarios
  -> freeboard and service-level check
  -> adaptation design decision
  -> review response
```

Task-card anchors:

- `slr-calculation`
- `freeboard-calculation`
- `outfall-submergence-check`
- `pump-head-calculation`
- `voltage-drop`

Source pack:

- asset register with levels;
- SLR scenario table;
- storm tide table;
- service-level criterion;
- adaptation option log.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change asset register with levels while keeping the downstream SLR and storm-tide scenarios fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make asset register with levels disagree with SLR scenario table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in storm tide table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on baseline asset level. The response should show SLR and storm-tide scenarios and freeboard and service-level check, then record review response using the same source values throughout.

### SSC-04-LH-07: Coastal Pump-Out And Generator Autonomy Package

This is a coastal, flood, and marine boundary work package for coastal pump-out and generator autonomy. It starts with the pump station section, flood level/event table, and pump curve or duty schedule.

The engineer checks pump duty and head, electrical load and generator/BESS sizing, and access/flooded equipment check. The output is the service continuity memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
flooded catchment or sump inflow
  -> pump duty and head
  -> electrical load and generator/BESS sizing
  -> access/flooded equipment check
  -> service continuity memo
```

Task-card anchors:

- `pump-head-calculation`
- `pump-power-efficiency`
- `battery-sizing`
- `bess-sizing-basic`
- `freeboard-calculation`

Source pack:

- pump station section;
- flood level/event table;
- pump curve or duty schedule;
- electrical load schedule;
- backup fuel or battery data.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change pump station section while keeping the downstream pump duty and head fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make pump station section disagree with flood level/event table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pump curve or duty schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on flooded catchment or sump inflow. The response should show pump duty and head and electrical load and generator/BESS sizing, then record service continuity memo using the same source values throughout.

### SSC-04-LH-08: Marine Asset Source-Policy And Review Packet

This is a coastal, flood, and marine boundary work package for marine asset source-policy and review packet. It starts with the datum statement, coastal criteria matrix, and marine asset schedule.

The engineer checks authority and datum selection, calculation trace, and review comments. The output is the acceptance or gap memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
coastal/marine source pack
  -> authority and datum selection
  -> calculation trace
  -> review comments
  -> acceptance or gap memo
```

Task-card anchors:

- `freeboard-calculation`
- `tidal-prism`
- `wave-runup`
- `fender-energy-check`
- `mooring-line-capacity`

Source pack:

- datum statement;
- coastal criteria matrix;
- marine asset schedule;
- calculation appendix;
- comment register.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change datum statement while keeping the downstream authority and datum selection fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make datum statement disagree with coastal criteria matrix about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in marine asset schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on coastal/marine design files. The response should show authority and datum selection and calculation trace, then record acceptance or gap memo using the same source values throughout.

## How The Variants Come Together

All `SSC-04` variants should use the same coastal and marine boundary workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the coastal and marine boundary package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-04-LH-01` | Coastal Flood, Outfall, Pump, And Electrical Elevation Package | `datum_frame` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-04-LH-02` | Wave Runup, Freeboard, And Asset Protection Package | `planning_horizon` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-04-LH-03` | Marine Berthing, Fender, And Storm Operations Package | `water_level_series` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-04-LH-04` | Flap Gate, Tide, And Drainage Resilience Package | `coastal_profile` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-04-LH-05` | Coastal Erosion, Longshore Transport, And Temporary Works Package | `marine_actions` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-04-LH-06` | Sea-Level-Rise Scenario And Asset-Level Review Package | `asset_elevations` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-04-LH-07` | Coastal Pump-Out And Generator Autonomy Package | `operating_event` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-04-LH-08` | Marine Asset Source-Policy And Review Packet | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The coastal package should keep the same datum, tide, sea-level allowance, wave climate, coastal profile, outfall level, freeboard, and exposed assets across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when the package is framed as a datum-and-event-controlled coastal boundary review. Normal work keeps tidal datum, survey datum, sea-level-rise scenario, planning horizon, wave or surge condition, asset levels, outfall levels, drainage tailwater, and authority criteria tied to the same event register.
- The useful long-horizon behaviour appears when coastal boundary conditions affect a second system: a stormwater outfall loses free discharge, a pump station needs raised electrical equipment, a marine asset changes operating mode, or an emergency-power package is sized for flood isolation.
- The current product list should not become generic flood prose. It needs explicit datum transforms, scenario IDs, water-level series, asset-elevation references, and source notes for uncertainty or planning-only tools.

Typical practitioner steps:

1. Establish survey and tidal datum frames, coastal profile, tide gauge or model basis, sea-level-rise/planning horizon, storm or wave case, and asset elevations.
2. Derive water levels, tailwater cases, freeboard, overtopping or runup checks, outfall/pump operating states, and marine-action assumptions using the same scenario ledger.
3. Check exposed civil, electrical, pump, outfall, marine, and temporary-works elements against the selected water-level and wave cases.
4. Issue a memo that names the datum conversion, scenario choice, water-level evidence, asset-level margins, operating constraints, and planning-only limitations.

Software stack notes:

- [NOAA Sea Level Rise Viewer](https://coast.noaa.gov/slr/) is a realistic planning and screening anchor for local sea-level scenarios, inundation, mapping confidence, high-tide flooding, and planning caveats.
- [NOAA Tides and Currents](https://tidesandcurrents.noaa.gov/) is a realistic source route for tide gauges, water levels, datums, and station evidence before the package turns coastal levels into engineering cases.
- [HEC-RAS](https://www.hec.usace.army.mil/software/hec-ras/) is a realistic hydraulic modelling anchor for riverine, floodplain, bridge/culvert, and 1D/2D unsteady boundary checks that interact with coastal tailwater.
- [USACE sea-level and coastal engineering resources](https://climate.sec.usace.army.mil/slat/) are realistic anchors for planning-horizon sea-level analysis and Corps-style coastal boundary workflows.

Design implications:

- Add `datum_frame_register`, `planning_horizon_scenario`, `water_level_series`, `coastal_profile`, `asset_elevation_register`, and `tailwater_case_ledger` fields before hardening `SSC-04-LH-01`.
- Treat planning viewers, tide-gauge records, hydraulic models, and design criteria as different evidence classes with different authority levels.
- Negative cases should include datum mismatch, sea-level scenario drift, an outfall check using the wrong tailwater, and an electrical elevation memo that ignores the selected flood event.

## Checks The Template Should Catch

These checks make `SSC-04` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `datum_frame` source object or evidence artifact. | `ssc_04_source_identity_mismatch` |
| Scenario drift | One stage uses a different `planning_horizon` case without a case-selection record. | `ssc_04_scenario_mismatch` |
| Geometry or topology drift | `water_level_series` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_04_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_04_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_04_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_04_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_04_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_04_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_04_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_04_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-04-LH-01` Coastal Flood, Outfall, Pump, And Electrical Elevation Package: start here because it uses the main coastal and marine boundary source files and produces a source-pack-sized memo.
2. `SSC-04-LH-02` Wave Runup, Freeboard, And Asset Protection Package: add this after the first source pack has stable source files and control values.
3. `SSC-04-LH-03` Marine Berthing, Fender, And Storm Operations Package: add this after the first source pack has stable source files and control values.
4. `SSC-04-LH-04` Flap Gate, Tide, And Drainage Resilience Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `coastal_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-04 product into a source pack.

A first executable-quality source pack for `SSC-04` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `coastal_source_manifest.yaml` | source fields such as `datum_frame`, `planning_horizon`, `water_level_series`, `coastal_profile`, `marine_actions` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `coastal_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `coastal_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as coastal and marine boundary product notes, while the source-pack build notes should be used only to guide later fixture packaging.
