# SSC-14 Structural load, support, foundation, and connection world Long-Horizon Design

This document treats supports, foundations, and connections as one source-controlled structural package: load schedule, member or bracket layout, foundation plan, connection details, material properties, and design cases have to line up. A useful long-horizon task keeps that structural basis consistent while moving between loads, supports, foundations, connections, wind, seismic, pipe, and equipment checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Structural source state | load schedule, support layout, foundation plan, connection/bracket/member schedule, material actions |
| Memberships | 46 task-card memberships |
| Primary cards | 17 |
| Disciplines | civil, electrical, ground, mechanical, structural |
| Score | 28/30 |
| Candidate product | Cross-discipline support/foundation package for pipe, facade, equipment, and retaining loads |
| Main risk | Very powerful but broad; must pick one physical support/foundation layout. |

The current card anchors cover load, support, foundation, connection, wind, seismic, pipe, facade, and equipment-support checks:

| Card | Plain-language role |
| --- | --- |
| `design-wind-pressure` | Calculates design wind pressure from wind speed and aerodynamic factors per AS/NZS 1170.2. |
| `design-wind-speed` | Site wind speed V_sit,beta from regional speed and multipliers per AS/NZS 1170.2. |
| `exit-gradient` | Calculates exit gradient at downstream toe and factor of safety against piping. |
| `fos-rapid-drawdown` | Calculates factor of safety for upstream slope during rapid reservoir drawdown. |
| `fos-seismic` | Factor of safety under pseudo-static seismic loading using the infinite slope method. |
| `fos-steady-state` | Factor of safety for embankment slope under steady-state seepage. |
| `hudson-armor-sizing` | Armor stone sizing using Hudson's equation W = rho_r * H^3 / (KD * (Sr-1)^3 * cot(alpha)). |
| `lateral-earth-pressure` | Active and passive earth pressures using Rankine or Coulomb theory. |
| `pipe-invert-calculation` | Downstream pipe invert level calculation for stormwater drainage. |
| `retaining-wall-stability` | Sliding, overturning, and bearing stability checks for gravity retaining walls. |

## Support And Foundation Data Model

Treat each task as a check against the same support and foundation package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-14`, the support and foundation package source state is:

```text
S_ssc_14 = {
  support_layout,
  load_schedule,
  connection_schedule,
  foundation_soil,
  equipment_or_asset_register,
  load_combinations,
  tolerance_constructability,
  authority_partition,
}
```

The product combinations below share the same support and foundation package data. A change to load schedule, support layout, foundation plan, bracket, connection, material property, or design case must carry through each check.

```text
W_ssc14_lh_01 x_S W_ssc14_lh_02
W_ssc14_lh_02 x_S W_ssc14_lh_03
W_ssc14_lh_03 x_S W_ssc14_lh_04
W_ssc14_lh_04 x_S W_ssc14_lh_05
W_ssc14_lh_05 x_S W_ssc14_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_14` | The support and foundation package source state that all combined checks must agree on. |
| `W_ssc14_lh_01` | The first SSC-14 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same support and foundation package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Support And Foundation Source Manifest

Any `SSC-14` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `support_layout` | Supports, brackets, anchors, members, foundations, pads, restraints, and grid. | support/foundation drawing |
| `load_schedule` | Dead, live, wind, seismic, thrust, equipment, thermal, and operating loads. | load table |
| `connection_schedule` | Anchor, bolt, weld, bracket, rail, member, and fixing identities. | connection schedule |
| `foundation_soil` | Bearing, uplift, groundwater, settlement, and geotechnical basis. | GI/foundation note |
| `equipment_or_asset_register` | Pipe, facade, pump, array, tank, wall, or mechanical asset supported. | asset schedule |
| `load_combinations` | ULS/SLS/service, event, temporary, and emergency combinations. | structural basis |
| `tolerance_constructability` | Setout, shim, movement, access, staging, and installation tolerances. | shop drawings |
| `authority_partition` | Structural, geotechnical, mechanical, facade, civil, electrical, and owner criteria split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-14-LH-01: Pipe Transient Support And Foundation Package

This is a structural support and foundation work package for pipe transient support and foundation. It starts with the pipe alignment/P&ID, transient/thrust event table, and support layout.

The engineer checks support/dead load reaction, foundation or bearing check, and load combination. The output is the support design memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
pipe transient or thrust event
  -> support/dead load reaction
  -> foundation or bearing check
  -> load combination
  -> support design memo
```

Task-card anchors:

- `thrust-force-calculation`
- `pipe-support-dead-load`
- `load-combinations`
- `terzaghi-bearing-capacity`
- `wall-bearing`

Source pack:

- pipe alignment/P&ID;
- transient/thrust event table;
- support layout;
- foundation detail;
- load case schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change pipe alignment/P&ID while keeping the downstream support/dead load reaction fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make pipe alignment/P&ID disagree with transient/thrust event table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in support layout only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on pipe transient or thrust event. The response should show support/dead load reaction and foundation or bearing check, then record support design memo using the same source values throughout.

### SSC-14-LH-02: Facade Or Roof Bracket, Anchor, And Connection Package

This is a structural support and foundation work package for facade or roof bracket, anchor, and connection. It starts with the facade/roof elevation, wind criteria, and bracket/anchor schedule.

The engineer checks bracket/anchor reaction, load combination, and material/certificate check. The output is the connection memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
wind pressure and tributary area
  -> bracket/anchor reaction
  -> load combination
  -> material/certificate check
  -> connection memo
```

Task-card anchors:

- `design-wind-pressure`
- `effective-wind-area`
- `bracket-load-calc`
- `load-combinations`
- `carbon-equivalent-calc`

Source pack:

- facade/roof elevation;
- wind criteria;
- bracket/anchor schedule;
- material certificate;
- load-case table.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change facade/roof elevation while keeping the downstream bracket/anchor reaction fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make facade/roof elevation disagree with wind criteria about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in bracket/anchor schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on wind pressure and tributary area. The response should show bracket/anchor reaction and load combination, then record connection memo using the same source values throughout.

### SSC-14-LH-03: Equipment Skid, Support, And Vibration Package

This is a structural support and foundation work package for equipment skid, support, and vibration. It starts with the equipment layout, mass/duty schedule, and support/foundation detail.

The engineer checks support reaction and foundation, vibration/fatigue check, and load combination. The output is the equipment support memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
equipment mass and duty
  -> support reaction and foundation
  -> vibration/fatigue check
  -> load combination
  -> equipment support memo
```

Task-card anchors:

- `pipe-support-dead-load`
- `vibration-transmissibility`
- `miner-fatigue`
- `load-combinations`
- `gravity-base-stability`

Source pack:

- equipment layout;
- mass/duty schedule;
- support/foundation detail;
- vibration/isolation data;
- load schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change equipment layout while keeping the downstream support reaction and foundation fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make equipment layout disagree with mass/duty schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in support/foundation detail only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on equipment mass and duty. The response should show support reaction and foundation and vibration/fatigue check, then record equipment support memo using the same source values throughout.

### SSC-14-LH-04: Retaining/Foundation Groundwater And Structural Stability Package

This is a structural support and foundation work package for retaining/foundation groundwater and structural stability. It starts with the ground report, wall section, and groundwater table.

The engineer checks earth pressure and surcharge, wall stability and foundation bearing, and uplift or settlement. The output is the retaining interface memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
soil/water state
  -> earth pressure and surcharge
  -> wall stability and foundation bearing
  -> uplift or settlement
  -> retaining interface memo
```

Task-card anchors:

- `lateral-earth-pressure`
- `retaining-wall-stability`
- `wall-overturning`
- `wall-bearing`
- `uplift-pressure`

Source pack:

- ground report;
- wall section;
- groundwater table;
- surcharge plan;
- foundation schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change ground report while keeping the downstream earth pressure and surcharge fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make ground report disagree with wall section about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in groundwater table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on soil/water state. The response should show earth pressure and surcharge and wall stability and foundation bearing, then record retaining interface memo using the same source values throughout.

### SSC-14-LH-05: Marine Fender, Mooring, And Berthing Structure Package

This is a structural support and foundation work package for marine fender, mooring, and berthing structure. It starts with the berth layout, vessel data, and fender/mooring schedule.

The engineer checks fender or mooring demand, support/load combination, and coastal water level case. The output is the marine structural memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
vessel/berthing scenario
  -> fender or mooring demand
  -> support/load combination
  -> coastal water level case
  -> marine structural memo
```

Task-card anchors:

- `berthing-energy-calc`
- `fender-energy-check`
- `mooring-line-capacity`
- `load-combinations`
- `freeboard-calculation`

Source pack:

- berth layout;
- vessel data;
- fender/mooring schedule;
- water-level table;
- structural detail.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change berth layout while keeping the downstream fender or mooring demand fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make berth layout disagree with vessel data about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in fender/mooring schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on vessel/berthing scenario. The response should show fender or mooring demand and support/load combination, then record marine structural memo using the same source values throughout.

### SSC-14-LH-06: Wind Turbine Or Solar Foundation Package

This is a structural support and foundation work package for wind turbine or solar foundation. It starts with the array/turbine layout, wind criteria, and foundation detail.

The engineer checks foundation geometry, soil bearing/stability, and connection/load combination. The output is the foundation memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
wind or PV/racking load
  -> foundation geometry
  -> soil bearing/stability
  -> connection/load combination
  -> foundation memo
```

Task-card anchors:

- `solar-array-wind-load`
- `gravity-base-stability`
- `design-wind-speed`
- `terzaghi-bearing-capacity`
- `load-combinations`

Source pack:

- array/turbine layout;
- wind criteria;
- foundation detail;
- geotechnical parameter table;
- connection/load schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change array/turbine layout while keeping the downstream foundation geometry fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make array/turbine layout disagree with wind criteria about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in foundation detail only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on wind or PV/racking load. The response should show foundation geometry and soil bearing/stability, then record foundation memo using the same source values throughout.

### SSC-14-LH-07: Construction Tolerance And Connection Repair Package

This is a structural support and foundation work package for construction tolerance and connection repair. It starts with the as-built survey, connection detail, and tolerance specification.

The engineer checks connection/bracket geometry, load or fit-up consequence, and repair option. The output is the field response memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
as-built tolerance measurement
  -> connection/bracket geometry
  -> load or fit-up consequence
  -> repair option
  -> field response memo
```

Task-card anchors:

- `construction-tolerance`
- `bracket-load-calc`
- `lap-splice-length`
- `load-combinations`
- `carbon-equivalent-calc`

Source pack:

- as-built survey;
- connection detail;
- tolerance specification;
- load check;
- field NCR/comment register.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change as-built survey while keeping the downstream connection/bracket geometry fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make as-built survey disagree with connection detail about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in tolerance specification only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on as-built tolerance measurement. The response should show connection/bracket geometry and load or fit-up consequence, then record field response memo using the same source values throughout.

### SSC-14-LH-08: Structural Review Packet And Authority Overlay

This is a structural support and foundation work package for structural review packet and authority overlay. It starts with the source index, load schedule, and material certificate.

The engineer checks governing load combinations, material/product evidence, and review comments. The output is the acceptance/gap response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
structural source pack
  -> governing load combinations
  -> material/product evidence
  -> review comments
  -> acceptance/gap response
```

Task-card anchors:

- `load-combinations`
- `sls-load-combinations`
- `uls-load-combinations`
- `carbon-equivalent-calc`
- `composite-section`

Source pack:

- source index;
- load schedule;
- material certificate;
- calculation appendix;
- comment register.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change source index while keeping the downstream governing load combinations fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make source index disagree with load schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in material certificate only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on structural design files. The response should show governing load combinations and material/product evidence, then record acceptance/gap response using the same source values throughout.

## How The Variants Come Together

All `SSC-14` variants should use the same support and foundation package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the support and foundation package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-14-LH-01` | Pipe Transient Support And Foundation Package | `support_layout` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-14-LH-02` | Facade Or Roof Bracket, Anchor, And Connection Package | `load_schedule` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-14-LH-03` | Equipment Skid, Support, And Vibration Package | `connection_schedule` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-14-LH-04` | Retaining/Foundation Groundwater And Structural Stability Package | `foundation_soil` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-14-LH-05` | Marine Fender, Mooring, And Berthing Structure Package | `equipment_or_asset_register` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-14-LH-06` | Wind Turbine Or Solar Foundation Package | `load_combinations` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-14-LH-07` | Construction Tolerance And Connection Repair Package | `tolerance_constructability` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-14-LH-08` | Structural Review Packet And Authority Overlay | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The support and foundation package should keep the same load schedule, support layout, foundation plan, connection details, material properties, and design cases across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when a single support or foundation layout has to satisfy structural actions, geotechnical reactions, product certificates, anchor/fixing design, and review comments.
- The important boundary is ownership: structural analysis, connection/anchor design, and foundation/soil checks are often run in different tools by different people. The package should check the handoff of reactions, load combinations, coordinates, support IDs, and selected products, rather than pretending one model owns the whole design.
- The first product remains a good hardening candidate because pipe transients create real support reactions that must be passed into structural/foundation checks.

Typical practitioner steps:

1. Establish support coordinates, foundation IDs, load cases/combinations, material grades, soil parameters, and connection/product options.
2. Run global/member analysis and extract reactions or demand envelopes.
3. Run connection, anchor, baseplate, bearing, foundation, or soil checks from those same reaction envelopes.
4. Issue a calculation package that ties load combinations, support IDs, product selections, governing utilizations, and review responses together.

Software stack notes:

- [SAP2000](https://www.csiamerica.com/products/sap2000) is a realistic structural model/analysis/design/reporting anchor for frames, shells, solids, and code-based design.
- [Tekla Tedds](https://www.tekla.com/products/tekla-tedds) is a realistic engineering-calculation/documentation anchor for structural load analysis, beam/column, connection, foundation, retaining-wall, and multi-code calculation packages.
- [Hilti PROFIS Engineering Suite](https://www.hilti.com/content/hilti/W1/US/en/business/business/engineering/profis-engineering.html) is a realistic anchor-design/report anchor for anchors, base plates, load-combination import, anchor layout, and code-referenced calculation reports.
- [PLAXIS](https://www.seequent.com/products-solutions/plaxis/) is a realistic deeper-analysis route when the support/foundation problem needs soil-structure interaction, deformation, groundwater, consolidation, or dynamic effects.

Design implications:

- Add `support_reaction_schedule`, `load_combination_register`, and `connection_design_report` fields before hardening `SSC-14-LH-01`.
- Require support IDs and coordinate references to survive across structural, anchor, and foundation checks.
- Negative cases should include load-combination mismatch, support-coordinate drift, and an anchor/foundation calculation using the wrong reaction envelope.

## Checks The Template Should Catch

These checks make `SSC-14` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `support_layout` source object or evidence artifact. | `ssc_14_source_identity_mismatch` |
| Scenario drift | One stage uses a different `load_schedule` case without a case-selection record. | `ssc_14_scenario_mismatch` |
| Geometry or topology drift | `connection_schedule` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_14_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_14_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_14_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_14_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_14_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_14_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_14_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_14_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-14-LH-01` Pipe Transient Support And Foundation Package: start here because it uses the main support and foundation package source files and produces a source-pack-sized memo.
2. `SSC-14-LH-02` Facade Or Roof Bracket, Anchor, And Connection Package: add this after the first source pack has stable source files and control values.
3. `SSC-14-LH-03` Equipment Skid, Support, And Vibration Package: add this after the first source pack has stable source files and control values.
4. `SSC-14-LH-04` Retaining/Foundation Groundwater And Structural Stability Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `support_foundation_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-14 product into a source pack.

A first executable-quality source pack for `SSC-14` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `support_foundation_source_manifest.yaml` | source fields such as `support_layout`, `load_schedule`, `connection_schedule`, `foundation_soil`, `equipment_or_asset_register` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `support_foundation_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `support_foundation_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as support and foundation package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
