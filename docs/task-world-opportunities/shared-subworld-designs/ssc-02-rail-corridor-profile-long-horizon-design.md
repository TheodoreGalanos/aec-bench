# SSC-02 Rail corridor profile, signalling, and OLE Long-Horizon Design

This document treats the rail corridor as one source-controlled design package: route chainage, gradients, speeds, signal locations, OLE spans, weather assumptions, and operating rules have to line up. A useful long-horizon task keeps that rail route consistent while moving between civil geometry, braking, signalling, OLE, drainage, power, and operator review.

## Evidence Basis

| Field | Value |
| --- | --- |
| Rail corridor source state | rail route profile, chainage, gradient, speed, signal layout, OLE span/weather envelope |
| Memberships | 12 task-card memberships |
| Primary cards | 10 |
| Disciplines | civil, electrical, mechanical |
| Score | 26/30 |
| Candidate product | Rail weather, OLE sag, signal sighting, braking, and drainage clearance |
| Main risk | Operator standards and sighting/STOPDIST evidence are harder to source publicly. |

The current card anchors cover rail profile, braking, signalling, OLE, level-crossing, and power checks:

| Card | Plain-language role |
| --- | --- |
| `cant-calculation` | Rail cant (superelevation) and cant deficiency for curved track using E_eq = 11.82 * V^2 / R. |
| `driveway-gradient-check` | Driveway gradient calculation and compliance check per AS/NZS 2890.1:2004. |
| `thermal-stress-calculation` | Rail thermal stress and force in CWR using sigma = E * alpha * dT (AREMA / ARTC). |
| `transition-spiral-length` | Minimum transition spiral length from cant runoff, cant deficiency rate of change, and twist criteria per ARTC ETS-05-00 / AREMA. |
| `vertical-curve-design` | Minimum vertical curve radius and length for railway grade transitions using R_v = V^2 / (3.6^2 * a_v). |
| `overlap-calculation` | Calculates rail signal overlap distance. |
| `power-load-calculation` | Signalling equipment connected load and supply kVA. |
| `signal-sighting-distance` | Rail signal sighting distance from reaction and braking distance. |
| `single-span-sag-tension` | Single span sag-tension calculation for overhead contact wires per EN 50119. |
| `warning-time-calculation` | Level crossing warning time and strike-in distance. |

## Rail Corridor Data Model

Treat each task as a check against the same rail corridor source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-02`, the rail corridor source state is:

```text
S_ssc_02 = {
  route_chainage,
  gradient_speed_case,
  signal_layout,
  ole_span_weather,
  drainage_clearance,
  rolling_stock_basis,
  operating_rule,
  authority_partition,
}
```

The product combinations below share the same rail corridor data. A change to route chainage, gradient, speed, signal location, OLE span, weather case, or operating rule must carry through each check.

```text
W_ssc02_lh_01 x_S W_ssc02_lh_02
W_ssc02_lh_02 x_S W_ssc02_lh_03
W_ssc02_lh_03 x_S W_ssc02_lh_04
W_ssc02_lh_04 x_S W_ssc02_lh_05
W_ssc02_lh_05 x_S W_ssc02_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_02` | The rail corridor source state that all combined checks must agree on. |
| `W_ssc02_lh_01` | The first SSC-02 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same rail corridor source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Rail Corridor Source Manifest

Any `SSC-02` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `route_chainage` | Route stationing for signals, gradients, spans, crossings, and drainage. | track profile, route diagram |
| `gradient_speed_case` | Line speed, grade, adhesion, braking, and operating restriction basis. | braking table, route standard |
| `signal_layout` | Signal, crossing, overlap, danger point, and sighting-object identities. | signal arrangement, sighting form |
| `ole_span_weather` | Span schedule, conductor/contact wire, temperature, wind, ice, and tension. | OLE span table, weather standard |
| `drainage_clearance` | Flood/freeboard state where rail assets share low-point or clearance constraints. | drainage long section, flood note |
| `rolling_stock_basis` | Train type, resistance, braking rate, mass, and emergency mode. | rolling-stock data sheet |
| `operating_rule` | Degraded weather, reduced speed, warning time, or possession rule. | operator standard, work instruction |
| `authority_partition` | Rail operator, signalling, OLE, civil drainage, and safety authority split. | standard matrix, review note |

## Candidate Long-Horizon Products

### SSC-02-LH-01: Rail Braking, Sighting, And Warning-Time Corridor Package

This is a rail corridor work package for rail braking, sighting, and warning-time corridor. It starts with the rail alignment profile, rolling-stock data sheet, and signal layout and sighting notes.

The engineer checks rolling-stock resistance and braking distance, signal sighting distance, and warning time and overlap check. The output is the operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
route profile and grade convention
  -> rolling-stock resistance and braking distance
  -> signal sighting distance
  -> warning time and overlap check
  -> operations memo
```

Task-card anchors:

- `davis-resistance`
- `braking-distance`
- `signal-sighting-distance`
- `warning-time-calculation`
- `overlap-calculation`

Source pack:

- rail alignment profile;
- rolling-stock data sheet;
- signal layout and sighting notes;
- level crossing parameters;
- operator rule excerpt.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change rail alignment profile while keeping the downstream rolling-stock resistance and braking distance fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make rail alignment profile disagree with rolling-stock data sheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in signal layout and sighting notes only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on route profile and grade convention. The response should show rolling-stock resistance and braking distance and signal sighting distance, then record operations memo using the same source values throughout.

### SSC-02-LH-02: OLE Sag, Thermal Stress, And Signal Clearance Package

This is a rail corridor work package for OLE sag, thermal stress, and signal clearance. It starts with the OLE span schedule, route profile and structure clearances, and weather/temperature table.

The engineer checks thermal stress and sag-tension state, clearance to signal or structure, and speed or weather restriction. The output is the clearance compliance memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
span and weather envelope
  -> thermal stress and sag-tension state
  -> clearance to signal or structure
  -> speed or weather restriction
  -> clearance compliance memo
```

Task-card anchors:

- `single-span-sag-tension`
- `thermal-stress-calculation`
- `static-thermal-rating`
- `signal-sighting-distance`
- `vertical-curve-design`

Source pack:

- OLE span schedule;
- route profile and structure clearances;
- weather/temperature table;
- conductor or wire data sheet;
- rail authority clearance criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change OLE span schedule while keeping the downstream thermal stress and sag-tension state fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make OLE span schedule disagree with route profile and structure clearances about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in weather/temperature table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on span and weather envelope. The response should show thermal stress and sag-tension state and clearance to signal or structure, then record clearance compliance memo using the same source values throughout.

### SSC-02-LH-03: Level Crossing Backup-Power And Degraded-Mode Operations

This is a rail corridor work package for level crossing backup-power and degraded-mode operations. It starts with the level crossing layout, warning-time worksheet, and controller and load schedule.

The engineer checks warning-time calculation, controller and communications load, and battery/generator autonomy. The output is the degraded-mode operations response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
approach profile and warning devices
  -> warning-time calculation
  -> controller and communications load
  -> battery/generator autonomy
  -> degraded-mode operations response
```

Task-card anchors:

- `warning-time-calculation`
- `power-load-calculation`
- `battery-sizing`
- `voltage-drop`
- `fiber-link-loss-budget`

Source pack:

- level crossing layout;
- warning-time worksheet;
- controller and load schedule;
- battery data sheet;
- operations standard or failure-mode note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change level crossing layout while keeping the downstream warning-time calculation fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make level crossing layout disagree with warning-time worksheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in controller and load schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on approach profile and warning devices. The response should show warning-time calculation and controller and communications load, then record degraded-mode operations response using the same source values throughout.

### SSC-02-LH-04: Rail Drainage, Flood Clearance, And Speed Restriction Package

This is a rail corridor work package for rail drainage, flood clearance, and speed restriction. It starts with the track profile and drainage long section, culvert or outfall schedule, and flood level table.

The engineer checks storm or tailwater case, track clearance or speed restriction, and signal/wayside asset exposure. The output is the flood resilience memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
route low point and drainage asset
  -> storm or tailwater case
  -> track clearance or speed restriction
  -> signal/wayside asset exposure
  -> flood resilience memo
```

Task-card anchors:

- `culvert-capacity`
- `hgl-check`
- `freeboard-calculation`
- `signal-sighting-distance`
- `davis-resistance`

Source pack:

- track profile and drainage long section;
- culvert or outfall schedule;
- flood level table;
- wayside equipment layout;
- operating restriction note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change track profile and drainage long section while keeping the downstream storm or tailwater case fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make track profile and drainage long section disagree with culvert or outfall schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in flood level table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on route low point and drainage asset. The response should show storm or tailwater case and track clearance or speed restriction, then record flood resilience memo using the same source values throughout.

### SSC-02-LH-05: Route Profile, Cant, And Rolling-Stock Braking Package

This is a rail corridor work package for route profile, cant, and rolling-stock braking. It starts with the alignment plan/profile, cant table, and rolling-stock data.

The engineer checks cant and transition calculation, rolling resistance and braking distance, and comfort or speed case. The output is the alignment operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
horizontal/vertical alignment
  -> cant and transition calculation
  -> rolling resistance and braking distance
  -> comfort or speed case
  -> alignment operations memo
```

Task-card anchors:

- `cant-calculation`
- `transition-spiral-length`
- `vertical-curve-design`
- `davis-resistance`
- `braking-distance`

Source pack:

- alignment plan/profile;
- cant table;
- rolling-stock data;
- speed and comfort criteria;
- operations scenario.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change alignment plan/profile while keeping the downstream cant and transition calculation fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make alignment plan/profile disagree with cant table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in rolling-stock data only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on horizontal/vertical alignment. The response should show cant and transition calculation and rolling resistance and braking distance, then record alignment operations memo using the same source values throughout.

### SSC-02-LH-06: Signal Overlap, Approach Speed, And Sighting Photo Package

This is a rail corridor work package for signal overlap, approach speed, and sighting photo. It starts with the signal arrangement plan, approach speed table, and sighting photo log or redrawn view.

The engineer checks sighting distance and field record, braking or stopping distance, and overlap calculation. The output is the sighting review response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
signal identity and approach speed
  -> sighting distance and field record
  -> braking or stopping distance
  -> overlap calculation
  -> sighting review response
```

Task-card anchors:

- `signal-sighting-distance`
- `overlap-calculation`
- `braking-distance`
- `ssd-on-grade`
- `warning-time-calculation`

Source pack:

- signal arrangement plan;
- approach speed table;
- sighting photo log or redrawn view;
- route gradient data;
- operator sighting criteria.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change signal arrangement plan while keeping the downstream sighting distance and field record fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make signal arrangement plan disagree with approach speed table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in sighting photo log or redrawn view only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on signal identity and approach speed. The response should show sighting distance and field record and braking or stopping distance, then record sighting review response using the same source values throughout.

### SSC-02-LH-07: Wayside Cabinet Load, Communications, And Backup Supply Package

This is a rail corridor work package for wayside cabinet load, communications, and backup supply. It starts with the cabinet layout, device load schedule, and communications topology.

The engineer checks communications topology, critical load register, and battery and feeder check. The output is the resilience note. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
wayside device inventory
  -> communications topology
  -> critical load register
  -> battery and feeder check
  -> resilience note
```

Task-card anchors:

- `power-load-calculation`
- `battery-sizing`
- `fiber-link-loss-budget`
- `voltage-drop`
- `rf-link-budget`

Source pack:

- cabinet layout;
- device load schedule;
- communications topology;
- battery or UPS data sheet;
- maintenance response plan.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change cabinet layout while keeping the downstream communications topology fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make cabinet layout disagree with device load schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in communications topology only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on wayside device inventory. The response should show communications topology and critical load register, then record resilience note using the same source values throughout.

### SSC-02-LH-08: Rail Standards Conflict And Operator Review Package

This is a rail corridor work package for rail standards conflict and operator review. It starts with the standards matrix, comment register, and alignment/signal design files.

The engineer checks operator standard selection, review comment or exception, and affected calculations. The output is the authority-partitioned response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
candidate design packet
  -> operator standard selection
  -> review comment or exception
  -> affected calculations
  -> authority-partitioned response
```

Task-card anchors:

- `warning-time-calculation`
- `signal-sighting-distance`
- `cant-calculation`
- `single-span-sag-tension`
- `overlap-calculation`

Source pack:

- standards matrix;
- comment register;
- alignment/signal source pack;
- calculation extracts;
- exception approval route.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change standards matrix while keeping the downstream operator standard selection fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make standards matrix disagree with comment register about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in alignment/signal source pack only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on candidate design packet. The response should show operator standard selection and review comment or exception, then record authority-partitioned response using the same source values throughout.

## How The Variants Come Together

All `SSC-02` variants should use the same rail corridor workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the rail corridor package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-02-LH-01` | Rail Braking, Sighting, And Warning-Time Corridor Package | `route_chainage` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-02-LH-02` | OLE Sag, Thermal Stress, And Signal Clearance Package | `gradient_speed_case` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-02-LH-03` | Level Crossing Backup-Power And Degraded-Mode Operations | `signal_layout` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-02-LH-04` | Rail Drainage, Flood Clearance, And Speed Restriction Package | `ole_span_weather` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-02-LH-05` | Route Profile, Cant, And Rolling-Stock Braking Package | `drainage_clearance` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-02-LH-06` | Signal Overlap, Approach Speed, And Sighting Photo Package | `rolling_stock_basis` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-02-LH-07` | Wayside Cabinet Load, Communications, And Backup Supply Package | `operating_rule` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-02-LH-08` | Rail Standards Conflict And Operator Review Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The rail corridor package should keep the same route profile, chainage, gradient, speed, signal layout, OLE spans, weather assumptions, and operating rules across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when a rail alignment/profile, chainage, gradient and speed case, signal layout, OLE span/weather envelope, drainage clearance, rolling-stock basis, and operating rule have to remain consistent across design and operator-review calculations.
- The long-horizon behaviour appears when the same corridor source affects braking or warning time, signal sighting, cant and vertical geometry, OLE sag/tension or clearance, drainage/flood restrictions, backup-power operation, and standards exceptions.
- Public evidence is uneven because operator standards, sighting forms, STOPDIST bundles, and signal plans can be controlled or private. The source pack should therefore separate public software/standards anchors from any task-owned redrawn corridor, signal, and OLE evidence.

Typical practitioner steps:

1. Establish route chainage, horizontal/vertical alignment, gradient and speed case, rolling-stock basis, signal and level-crossing layout, OLE spans, weather/design assumptions, and operator standards.
2. Check geometry, cant, braking or warning time, signal sighting/overlap, OLE sag/clearance, drainage/flood constraints, and degraded-mode or backup-power operation.
3. Reconcile discipline outputs against operator standards, safety requirements, exceptions, and review comments.
4. Issue a corridor or signalling response that ties chainage, design case, source drawings, calculation extracts, standard selection, and authority decisions together.

Software stack notes:

- [Bentley OpenRail Designer](https://www.bentley.com/software/openrail-designer/) is a realistic rail-design anchor for corridors, profiles, cross sections, track regressions, cant, signals, drainage, geometry, yards, stations, and sidings.
- [OpenTrack](http://www.opentrack.ch/opentrack/opentrack_e/opentrack_e.html) is a realistic rail-operations simulation route when timetable, rolling stock, signalling, and infrastructure assumptions need operational testing.
- [ERA ERTMS](https://www.era.europa.eu/domains/infrastructure/european-rail-traffic-management-system-ertms_en) is a realistic signalling and train-control standards anchor for ETCS, ERTMS specifications, interoperability, and braking-curve material.
- [Network Rail standards for suppliers](https://www.networkrail.co.uk/industry-and-commercial/supply-chain/standards-for-suppliers/) is a realistic operator-standards route, while local projects may need ARTC, state rail, or other operator-specific standards instead.

Design implications:

- Add `route_chainage_register`, `gradient_speed_case_register`, `signal_layout_register`, and `operator_standard_register` fields before hardening `SSC-02-LH-01`.
- Require chainage, signal IDs, OLE span IDs, speed/gradient cases, rolling-stock basis, and operator-standard references to survive across braking, sighting, OLE, drainage, and review outputs.
- Negative cases should include chainage drift, wrong speed case, signal-ID mismatch, OLE/weather basis swap, private-standard overclaim, and a review response that collapses operator and design-authority requirements.

## Checks The Template Should Catch

These checks make `SSC-02` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `route_chainage` source object or evidence artifact. | `ssc_02_source_identity_mismatch` |
| Scenario drift | One stage uses a different `gradient_speed_case` case without a case-selection record. | `ssc_02_scenario_mismatch` |
| Geometry or topology drift | `signal_layout` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_02_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_02_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_02_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_02_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_02_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_02_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_02_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_02_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-02-LH-01` Rail Braking, Sighting, And Warning-Time Corridor Package: start here because it uses the main rail corridor source files and produces a source-pack-sized memo.
2. `SSC-02-LH-02` OLE Sag, Thermal Stress, And Signal Clearance Package: add this after the first source pack has stable source files and control values.
3. `SSC-02-LH-03` Level Crossing Backup-Power And Degraded-Mode Operations: add this after the first source pack has stable source files and control values.
4. `SSC-02-LH-04` Rail Drainage, Flood Clearance, And Speed Restriction Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `rail_corridor_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-02 product into a source pack.

A first executable-quality source pack for `SSC-02` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `rail_corridor_source_manifest.yaml` | source fields such as `route_chainage`, `gradient_speed_case`, `signal_layout`, `ole_span_weather`, `drainage_clearance` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `rail_corridor_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `rail_corridor_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as rail corridor product notes, while the source-pack build notes should be used only to guide later fixture packaging.
