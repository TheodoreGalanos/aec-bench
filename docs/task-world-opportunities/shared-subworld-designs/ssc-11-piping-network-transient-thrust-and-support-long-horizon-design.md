# SSC-11 Piping network, transient, thrust, and support world Long-Horizon Design

This document treats the pipe network as one source-controlled package: alignment, nodes, pipe sizes, valves, supports, restraints, transient event, and foundation interfaces have to line up. A useful long-horizon task keeps that piping basis consistent while moving between headloss, HGL, surge, thrust, support, restraint, protection, and foundation checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Piping source state | P&ID/pipe alignment, supports, restraints, transient event, thrust block/foundation interfaces |
| Memberships | 35 task-card memberships |
| Primary cards | 11 |
| Disciplines | civil, electrical, ground, mechanical, structural |
| Score | 28/30 |
| Candidate product | Pipe transient to support/foundation and protection-trip package |
| Main risk | Transient event definition and support/foundation geometry must be source-owned. |

The current card anchors cover pipe headloss, HGL, transient, valve, thrust, restraint, support, and foundation checks:

| Card | Plain-language role |
| --- | --- |
| `darcy-weisbach-headloss` | Friction head loss calculation using Darcy-Weisbach equation with Swamee-Jain friction factor. |
| `exit-gradient` | Calculates exit gradient at downstream toe and factor of safety against piping. |
| `flap-gate-headloss` | Flap gate headloss calculation for stormwater outfalls. |
| `fos-rapid-drawdown` | Calculates factor of safety for upstream slope during rapid reservoir drawdown. |
| `fos-seismic` | Factor of safety under pseudo-static seismic loading using the infinite slope method. |
| `fos-steady-state` | Factor of safety for embankment slope under steady-state seepage. |
| `hazen-williams-headloss` | Friction head loss calculation using the Hazen-Williams empirical equation. |
| `hgl-check` | Hydraulic grade line check for a single stormwater pipe reach. |
| `lateral-earth-pressure` | Active and passive earth pressures using Rankine or Coulomb theory. |
| `linear-wave-theory` | Linear (Airy) wave theory: wavelength, celerity, and group velocity via dispersion relation (USACE CEM). |

## Piping Network Data Model

Treat each task as a check against the same piping network package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-11`, the piping network package source state is:

```text
S_ssc_11 = {
  pipe_alignment,
  hydraulic_state,
  transient_event,
  thrust_supports,
  equipment_controls,
  soil_foundation,
  operating_scenario,
  authority_partition,
}
```

The product combinations below share the same piping network package data. A change to pipe alignment, node, pipe size, valve, support, restraint, transient event, or foundation interface must carry through each check.

```text
W_ssc11_lh_01 x_S W_ssc11_lh_02
W_ssc11_lh_02 x_S W_ssc11_lh_03
W_ssc11_lh_03 x_S W_ssc11_lh_04
W_ssc11_lh_04 x_S W_ssc11_lh_05
W_ssc11_lh_05 x_S W_ssc11_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_11` | The piping network package source state that all combined checks must agree on. |
| `W_ssc11_lh_01` | The first SSC-11 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same piping network package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Piping Source Manifest

Any `SSC-11` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `pipe_alignment` | Pipe segments, nodes, invert levels, supports, restraints, and outfalls. | P&ID/alignment |
| `hydraulic_state` | Flow, headloss, HGL, pump state, valve state, and tailwater. | hydraulic model |
| `transient_event` | Pump trip, valve closure, surge, water hammer, or emergency case. | transient study |
| `thrust_supports` | Thrust blocks, anchors, supports, foundations, restraints. | support drawing |
| `equipment_controls` | Pump/motor, valve, protection, instrumentation, and trip settings. | control/SLD |
| `soil_foundation` | Bearing, uplift, groundwater, and geotechnical support. | GI/foundation note |
| `operating_scenario` | Normal, fire, startup, shutdown, outage, or blocked outlet case. | operation note |
| `authority_partition` | Hydraulic, mechanical, structural, electrical, geotechnical, and fire criteria split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-11-LH-01: Pump Transient, Thrust, Support, And Protection-Trip Package

This is a piping network and support work package for pump transient, thrust, support, and protection-trip. It starts with the P&ID or pipe alignment, pump/control scenario, and transient event table.

The engineer checks transient event/wave speed, thrust force and support reaction, and protection trip or pump control. The output is the support/protection memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
pipe alignment and steady duty
  -> transient event/wave speed
  -> thrust force and support reaction
  -> protection trip or pump control
  -> support/protection memo
```

Task-card anchors:

- `wave-speed-calculation`
- `joukowsky-pressure`
- `thrust-force-calculation`
- `pipe-support-dead-load`
- `pump-head-calculation`

Source pack:

- P&ID or pipe alignment;
- pump/control scenario;
- transient event table;
- support/foundation detail;
- protection/control settings.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change P&ID or pipe alignment while keeping the downstream transient event/wave speed fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make P&ID or pipe alignment disagree with pump/control scenario about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in transient event table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on pipe alignment and steady duty. The response should show transient event/wave speed and thrust force and support reaction, then record support/protection memo using the same source values throughout.

### SSC-11-LH-02: Fire-Main Hydraulic And Seismic Support Package

This is a piping network and support work package for fire-main hydraulic and seismic support. It starts with the fire main schematic, flow/demand table, and pipe/support layout.

The engineer checks main/riser hydraulic loss, seismic or support layout, and pump/pressure branch. The output is the fire-main design memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
fire-flow demand
  -> main/riser hydraulic loss
  -> seismic or support layout
  -> pump/pressure branch
  -> fire-main design memo
```

Task-card anchors:

- `friction-loss-hazen-williams`
- `available-flow-calculation`
- `sprinkler-discharge`
- `pipe-support-dead-load`
- `lateral-earth-pressure`

Source pack:

- fire main schematic;
- flow/demand table;
- pipe/support layout;
- pump curve or hydrant test;
- fire code/authority criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change fire main schematic while keeping the downstream main/riser hydraulic loss fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make fire main schematic disagree with flow/demand table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pipe/support layout only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on fire-flow demand. The response should show main/riser hydraulic loss and seismic or support layout, then record fire-main design memo using the same source values throughout.

### SSC-11-LH-03: Process Piping Valve And Control Package

This is a piping network and support work package for process piping valve and control. It starts with the P&ID, line list, and valve data sheet.

The engineer checks valve Cv or pressure-loss check, 4-20 mA control signal, and support or thrust effect. The output is the process piping memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
process flow and pipe network
  -> valve Cv or pressure-loss check
  -> 4-20 mA control signal
  -> support or thrust effect
  -> process piping memo
```

Task-card anchors:

- `cv-liquid-incompressible`
- `pressure-loss-calculation`
- `4-20ma-scaling`
- `thrust-force-calculation`
- `velocity-check`

Source pack:

- P&ID;
- line list;
- valve data sheet;
- loop schedule;
- support schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change P&ID while keeping the downstream valve Cv or pressure-loss check fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make P&ID disagree with line list about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in valve data sheet only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on process flow and pipe network. The response should show valve Cv or pressure-loss check and 4-20 mA control signal, then record process piping memo using the same source values throughout.

### SSC-11-LH-04: Stormwater Outlet, Flap Gate, And Pipe HGL Package

This is a piping network and support work package for stormwater outlet, flap gate, and pipe HGL. It starts with the drainage long section, flap gate data, and tailwater table.

The engineer checks tailwater/flap gate boundary, headloss and HGL, and support or outfall structure. The output is the outlet memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
storm pipe alignment
  -> tailwater/flap gate boundary
  -> headloss and HGL
  -> support or outfall structure
  -> outlet memo
```

Task-card anchors:

- `flap-gate-headloss`
- `hgl-check`
- `mannings-pipe-capacity`
- `pipe-support-dead-load`
- `outfall-submergence-check`

Source pack:

- drainage long section;
- flap gate data;
- tailwater table;
- pipe schedule;
- outfall/support detail.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change drainage long section while keeping the downstream tailwater/flap gate boundary fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make drainage long section disagree with flap gate data about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in tailwater table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on storm pipe alignment. The response should show tailwater/flap gate boundary and headloss and HGL, then record outlet memo using the same source values throughout.

### SSC-11-LH-05: Buried Pipeline Groundwater And Uplift Package

This is a piping network and support work package for buried pipeline groundwater and uplift. It starts with the pipe profile, soil/groundwater report, and pressure table.

The engineer checks groundwater and soil case, uplift/exit or bedding check, and hydraulic pressure state. The output is the buried pipeline memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
buried pipe profile
  -> groundwater and soil case
  -> uplift/exit or bedding check
  -> hydraulic pressure state
  -> buried pipeline memo
```

Task-card anchors:

- `uplift-pressure`
- `exit-gradient`
- `hazen-williams-headloss`
- `pipe-velocity-check`
- `lateral-earth-pressure`

Source pack:

- pipe profile;
- soil/groundwater report;
- pressure table;
- bedding/support detail;
- construction staging note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change pipe profile while keeping the downstream groundwater and soil case fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make pipe profile disagree with soil/groundwater report about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pressure table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on buried pipe profile. The response should show groundwater and soil case and uplift/exit or bedding check, then record buried pipeline memo using the same source values throughout.

### SSC-11-LH-06: Pump Station Rising Main Energy And Surge Package

This is a piping network and support work package for pump station rising main energy and surge. It starts with the pump curve, rising-main profile, and pipe schedule.

The engineer checks steady losses and power, surge event, and feeder or trip consequence. The output is the rising main memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
pump duty and rising main
  -> steady losses and power
  -> surge event
  -> feeder or trip consequence
  -> rising main memo
```

Task-card anchors:

- `pump-head-calculation`
- `hazen-williams-friction`
- `pump-power-efficiency`
- `joukowsky-pressure`
- `voltage-drop`

Source pack:

- pump curve;
- rising-main profile;
- pipe schedule;
- motor/feeder schedule;
- trip/control narrative.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change pump curve while keeping the downstream steady losses and power fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make pump curve disagree with rising-main profile about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pipe schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on pump duty and rising main. The response should show steady losses and power and surge event, then record rising main memo using the same source values throughout.

### SSC-11-LH-07: Pipe Material/Product And Velocity Compliance Package

This is a piping network and support work package for pipe material/product and velocity compliance. It starts with the line list, material datasheet/certificate, and velocity/loss criteria.

The engineer checks velocity/pressure loss, product certificate or lining limit, and support/foundation branch. The output is the product compliance memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
line list and material class
  -> velocity/pressure loss
  -> product certificate or lining limit
  -> support/foundation branch
  -> product compliance memo
```

Task-card anchors:

- `pipe-velocity-check`
- `pressure-loss-calculation`
- `carbon-equivalent-calc`
- `pipe-support-dead-load`
- `por-aor-compliance`

Source pack:

- line list;
- material datasheet/certificate;
- velocity/loss criteria;
- support schedule;
- review comments.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change line list while keeping the downstream velocity/pressure loss fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make line list disagree with material datasheet/certificate about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in velocity/loss criteria only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on line list and material class. The response should show velocity/pressure loss and product certificate or lining limit, then record product compliance memo using the same source values throughout.

### SSC-11-LH-08: Piping Network Repair And Negative-Case Portfolio

This is a piping network and support work package for piping network repair and negative-case portfolio. It starts with the baseline P&ID, variant line list, and support detail.

The engineer checks controlled line/valve/support mutation, expected changed handoffs, and localized failure stage. The output is the repair response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
baseline network source pack
  -> controlled line/valve/support mutation
  -> expected changed handoffs
  -> localized failure stage
  -> repair response
```

Task-card anchors:

- `darcy-weisbach-headloss`
- `minor-losses-calculation`
- `thrust-force-calculation`
- `velocity-check`
- `wave-speed-calculation`

Source pack:

- baseline P&ID;
- variant line list;
- support detail;
- verification cases;
- answer examples.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change baseline P&ID while keeping the downstream controlled line/valve/support mutation fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make baseline P&ID disagree with variant line list about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in support detail only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on baseline network design files. The response should show controlled line/valve/support mutation and expected changed handoffs, then record repair response using the same source values throughout.

## How The Variants Come Together

All `SSC-11` variants should use the same piping network package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the piping network package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-11-LH-01` | Pump Transient, Thrust, Support, And Protection-Trip Package | `pipe_alignment` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-11-LH-02` | Fire-Main Hydraulic And Seismic Support Package | `hydraulic_state` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-11-LH-03` | Process Piping Valve And Control Package | `transient_event` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-11-LH-04` | Stormwater Outlet, Flap Gate, And Pipe HGL Package | `thrust_supports` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-11-LH-05` | Buried Pipeline Groundwater And Uplift Package | `equipment_controls` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-11-LH-06` | Pump Station Rising Main Energy And Surge Package | `soil_foundation` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-11-LH-07` | Pipe Material/Product And Velocity Compliance Package | `operating_scenario` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-11-LH-08` | Piping Network Repair And Negative-Case Portfolio | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The piping package should keep the same pipe alignment, nodes, pipe sizes, valves, supports, restraints, transient event, and foundation interfaces across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when a pipeline package joins hydraulic steady-state modelling, transient event definition, thrust restraint, pipe supports, foundation reactions, pump/protection trips, and pipe stress.
- The transient event must be explicit before the support/foundation work can trust the forces. Valve-closure curves, pump trips, check-valve behaviour, wave speed, air valves, surge tanks, and operating cases are not optional context.
- The first product is a strong hardening candidate because it has a clean engineering handoff: transient pressures/forces from the hydraulic model become support, thrust, pipe-stress, and protection-trip requirements.

Typical practitioner steps:

1. Build the baseline pipe network with nodes, elevations, pipe sizes, materials, pumps, valves, restraints, supports, and operating cases.
2. Define transient events such as pump trip/restart, valve closure, emergency shutdown, check-valve slam, or surge-device operation.
3. Run hydraulic/transient analysis and export pressures, unbalanced forces, support reactions, or design envelopes.
4. Check thrust blocks, pipe supports, stress, foundation/interface loads, and protection settings from the same event table.

Software stack notes:

- [OpenFlows Water](https://www.bentley.com/software/openflows-water/) is a realistic water-distribution modelling anchor; its tiers include WaterCAD/WaterGEMS and HAMMER for hydraulic transient analysis.
- [Impulse](https://www.datacor.com/products/impulse) is a realistic water-hammer/surge anchor for pressure surges, pump trips/restarts, valve operations, wave speed, cavitation, surge protection, and exporting transient forces to stress tools.
- [AutoPIPE](https://www.bentley.com/software/autopipe/) is a realistic pipe-stress anchor for static structural analysis plus advanced buried-pipe, flange, force-time-history, fluid-transient, stress, seismic, and code-based checks.

Design implications:

- Add `transient_event_table`, `surge_device_schedule`, and `pipe_support_reaction_table` fields before hardening `SSC-11-LH-01`.
- Treat exported transient forces as scenario-bound values; they must carry event ID, wave speed, valve/pump curve, and timestamp or envelope basis.
- Negative cases should include exporting forces from the wrong transient event, reusing steady-state pressure as surge pressure, and changing support geometry after force export.

## Checks The Template Should Catch

These checks make `SSC-11` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `pipe_alignment` source object or evidence artifact. | `ssc_11_source_identity_mismatch` |
| Scenario drift | One stage uses a different `hydraulic_state` case without a case-selection record. | `ssc_11_scenario_mismatch` |
| Geometry or topology drift | `transient_event` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_11_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_11_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_11_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_11_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_11_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_11_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_11_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_11_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-11-LH-01` Pump Transient, Thrust, Support, And Protection-Trip Package: start here because it uses the main piping network package source files and produces a source-pack-sized memo.
2. `SSC-11-LH-02` Fire-Main Hydraulic And Seismic Support Package: add this after the first source pack has stable source files and control values.
3. `SSC-11-LH-03` Process Piping Valve And Control Package: add this after the first source pack has stable source files and control values.
4. `SSC-11-LH-04` Stormwater Outlet, Flap Gate, And Pipe HGL Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `piping_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-11 product into a source pack.

A first executable-quality source pack for `SSC-11` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `piping_source_manifest.yaml` | source fields such as `pipe_alignment`, `hydraulic_state`, `transient_event`, `thrust_supports`, `equipment_controls` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `piping_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `piping_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as piping network package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
