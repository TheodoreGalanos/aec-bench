# SSC-18 Instrumentation, controls, valve, and process signal world Long-Horizon Design

This document treats instrumentation and control as one source-controlled loop package: P&ID tags, process values, valve data, signal ranges, alarm limits, control actions, and protection settings have to line up. A useful long-horizon task keeps that control basis consistent while moving between valve sizing, signal scaling, process checks, alarms, interlocks, and control narratives.

## Evidence Basis

| Field | Value |
| --- | --- |
| Control source state | P&ID, loop schedule, valve datasheet, 4-20 mA range, control/protection settings |
| Memberships | 2 task-card memberships |
| Primary cards | 2 |
| Disciplines | electrical |
| Score | 15/30 |
| Candidate product | Instrumentation/control package tying process value, valve Cv, signal scaling, and protection settings |
| Main risk | Current catalogue substrate is thin; likely a follow-up after process/piping worlds. |

The current card anchors cover valve, process value, 4-20 mA signal, control loop, alarm, and protection-setting checks:

| Card | Plain-language role |
| --- | --- |
| `cv-liquid-incompressible` | Control valve Cv sizing for incompressible liquid service per ISA-75.01.01. |
| `4-20ma-scaling` | Linear process variable scaling to a 4-20 mA signal. |

## Control Loop Data Model

Treat each task as a check against the same instrumentation and control package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-18`, the instrumentation and control package source state is:

```text
S_ssc_18 = {
  tag_register,
  process_value_basis,
  valve_or_device_data,
  signal_range,
  control_mode,
  network_power,
  commissioning_evidence,
  authority_partition,
}
```

The product combinations below share the same instrumentation and control package data. A change to P&ID tag, process value, valve data, signal range, alarm limit, control action, or protection setting must carry through each check.

```text
W_ssc18_lh_01 x_S W_ssc18_lh_02
W_ssc18_lh_02 x_S W_ssc18_lh_03
W_ssc18_lh_03 x_S W_ssc18_lh_04
W_ssc18_lh_04 x_S W_ssc18_lh_05
W_ssc18_lh_05 x_S W_ssc18_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_18` | The instrumentation and control package source state that all combined checks must agree on. |
| `W_ssc18_lh_01` | The first SSC-18 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same instrumentation and control package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Control Source Manifest

Any `SSC-18` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `tag_register` | Instrument, valve, loop, controller, alarm, and asset tag identities. | P&ID/loop index |
| `process_value_basis` | Flow, pressure, level, temperature, fluid, and operating range. | process data sheet |
| `valve_or_device_data` | Cv, trim, actuator, fail state, pressure drop, and limits. | valve datasheet |
| `signal_range` | 4-20 mA, scaling, engineering units, calibration, and alarm setpoints. | loop sheet |
| `control_mode` | Manual, auto, fail-safe, interlock, trip, degraded, or commissioning state. | control narrative |
| `network_power` | I/O, PLC, SCADA, PoE, UPS, or cabinet constraints. | control panel schedule |
| `commissioning_evidence` | Calibration, range check, loop test, and acceptance records. | test sheet |
| `authority_partition` | Process, controls, electrical, safety, and owner authority split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-18-LH-01: Valve Cv, Process Value, And Signal Scaling Package

This is a instrumentation and controls work package for valve cv, process value, and signal scaling. It starts with the P&ID, valve datasheet, and process range table.

The engineer checks valve Cv calculation, 4-20 mA range and scaling, and control setpoint consequence. The output is the loop memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
process flow/pressure basis
  -> valve Cv calculation
  -> 4-20 mA range and scaling
  -> control setpoint consequence
  -> loop memo
```

Task-card anchors:

- `cv-liquid-incompressible`
- `4-20ma-scaling`
- `pressure-loss-calculation`
- `mass-balance`
- `voltage-drop`

Source pack:

- P&ID;
- valve datasheet;
- process range table;
- loop schedule;
- control narrative.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change P&ID while keeping the downstream valve Cv calculation fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make P&ID disagree with valve datasheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in process range table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on process flow/pressure basis. The response should show valve Cv calculation and 4-20 mA range and scaling, then record loop memo using the same source values throughout.

### SSC-18-LH-02: Stormwater Or Treatment Telemetry Control Package

This is a instrumentation and controls work package for stormwater or treatment telemetry control. It starts with the sensor schedule, level/flow table, and control narrative.

The engineer checks instrument range and scaling, control/pump/gate response, and backup power/comms. The output is the telemetry memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
process or water level variable
  -> instrument range and scaling
  -> control/pump/gate response
  -> backup power/comms
  -> telemetry memo
```

Task-card anchors:

- `4-20ma-scaling`
- `poe-power-budget`
- `battery-sizing`
- `hgl-check`
- `pump-power-calculation`

Source pack:

- sensor schedule;
- level/flow table;
- control narrative;
- communications topology;
- power schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change sensor schedule while keeping the downstream instrument range and scaling fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make sensor schedule disagree with level/flow table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in control narrative only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on process or water level variable. The response should show instrument range and scaling and control/pump/gate response, then record telemetry memo using the same source values throughout.

### SSC-18-LH-03: Protection And Control Setting Bridge To SLD

This is a instrumentation and controls work package for protection and control setting bridge to SLD. It starts with the SLD, protection setting table, and instrument transformer data.

The engineer checks signal/range scaling, protection/control setting, and SLD or feeder consequence. The output is the control-setting memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
electrical measurement or fault variable
  -> signal/range scaling
  -> protection/control setting
  -> SLD or feeder consequence
  -> control-setting memo
```

Task-card anchors:

- `4-20ma-scaling`
- `three-phase-fault-current`
- `incident-energy`
- `voltage-drop`
- `power-load-calculation`

Source pack:

- SLD;
- protection setting table;
- instrument transformer data;
- loop schedule;
- fault/load table.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change SLD while keeping the downstream signal/range scaling fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make SLD disagree with protection setting table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in instrument transformer data only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on electrical measurement or fault variable. The response should show signal/range scaling and protection/control setting, then record control-setting memo using the same source values throughout.

### SSC-18-LH-04: Commissioning And Calibration Review Packet

This is a instrumentation and controls work package for commissioning and calibration review packet. It starts with the commissioning checklist, calibration sheet, and valve datasheet.

The engineer checks calibration range and acceptance, loop check or failed point, and affected process result. The output is the commissioning response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
instrument/valve source pack
  -> calibration range and acceptance
  -> loop check or failed point
  -> affected process result
  -> commissioning response
```

Task-card anchors:

- `4-20ma-scaling`
- `cv-liquid-incompressible`
- `mass-balance`
- `pressure-loss-calculation`
- `por-aor-compliance`

Source pack:

- commissioning checklist;
- calibration sheet;
- valve datasheet;
- loop schedule;
- process acceptance criteria.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change commissioning checklist while keeping the downstream calibration range and acceptance fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make commissioning checklist disagree with calibration sheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in valve datasheet only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on instrument/valve design files. The response should show calibration range and acceptance and loop check or failed point, then record commissioning response using the same source values throughout.

### SSC-18-LH-05: Chemical Dosing Flowmeter And Control Package

This is a instrumentation and controls work package for chemical dosing flowmeter and control. It starts with the chemical dosing basis, flowmeter datasheet, and pump/valve schedule.

The engineer checks flowmeter/signal scaling, pump or valve duty, and alarm/control branch. The output is the dosing control memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
chemical dose and flow range
  -> flowmeter/signal scaling
  -> pump or valve duty
  -> alarm/control branch
  -> dosing control memo
```

Task-card anchors:

- `chemical-dosing`
- `4-20ma-scaling`
- `cv-liquid-incompressible`
- `pump-power-calculation`
- `voltage-drop`

Source pack:

- chemical dosing basis;
- flowmeter datasheet;
- pump/valve schedule;
- loop range table;
- alarm setpoint note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change chemical dosing basis while keeping the downstream flowmeter/signal scaling fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make chemical dosing basis disagree with flowmeter datasheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pump/valve schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on chemical dose and flow range. The response should show flowmeter/signal scaling and pump or valve duty, then record dosing control memo using the same source values throughout.

### SSC-18-LH-06: Fire Pump Pressure Signal And Alarm Package

This is a instrumentation and controls work package for fire pump pressure signal and alarm. It starts with the fire pump schematic, pressure sensor data sheet, and alarm threshold table.

The engineer checks sensor range and alarm threshold, pump/control consequence, and battery/NAC load. The output is the fire control memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
fire-water pressure/flow state
  -> sensor range and alarm threshold
  -> pump/control consequence
  -> battery/NAC load
  -> fire control memo
```

Task-card anchors:

- `available-flow-calculation`
- `water-supply-curve`
- `4-20ma-scaling`
- `nac-load-calculation`
- `battery-sizing`

Source pack:

- fire pump schematic;
- pressure sensor data sheet;
- alarm threshold table;
- NAC/load schedule;
- fire authority criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change fire pump schematic while keeping the downstream sensor range and alarm threshold fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make fire pump schematic disagree with pressure sensor data sheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in alarm threshold table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on fire-water pressure/flow state. The response should show sensor range and alarm threshold and pump/control consequence, then record fire control memo using the same source values throughout.

### SSC-18-LH-07: Valve Failure And Safe-State Repair Package

This is a instrumentation and controls work package for valve failure and safe-state repair. It starts with the P&ID, valve datasheet, and loop schedule.

The engineer checks failed signal or valve authority, hydraulic/process consequence, and safe-state branch. The output is the repair response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
baseline valve/control state
  -> failed signal or valve authority
  -> hydraulic/process consequence
  -> safe-state branch
  -> repair response
```

Task-card anchors:

- `cv-liquid-incompressible`
- `4-20ma-scaling`
- `hgl-check`
- `pressure-loss-calculation`
- `mass-balance`

Source pack:

- P&ID;
- valve datasheet;
- loop schedule;
- failure mode table;
- control narrative.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change P&ID while keeping the downstream failed signal or valve authority fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make P&ID disagree with valve datasheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in loop schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on baseline valve/control state. The response should show failed signal or valve authority and hydraulic/process consequence, then record repair response using the same source values throughout.

### SSC-18-LH-08: Instrumentation Source-Policy And Thin-Substrate Extension Package

This is a instrumentation and controls work package for instrumentation source-policy and thin-substrate extension. It starts with the source index, P&ID/loop schedule, and linked process/electrical tables.

The engineer checks linked process/electrical world, explicit missing template substrate, and verification cases. The output is the extension memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
control source pack
  -> linked process/electrical world
  -> explicit missing template substrate
  -> verification cases
  -> extension memo
```

Task-card anchors:

- `4-20ma-scaling`
- `cv-liquid-incompressible`
- `oxygen-requirements`
- `voltage-drop`
- `battery-sizing`

Source pack:

- source index;
- P&ID/loop schedule;
- linked process/electrical tables;
- verification cases;
- gap register.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change source index while keeping the downstream linked process/electrical world fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make source index disagree with P&ID/loop schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in linked process/electrical tables only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on control design files. The response should show linked process/electrical world and explicit missing template substrate, then record extension memo using the same source values throughout.

## How The Variants Come Together

All `SSC-18` variants should use the same instrumentation and control package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the instrumentation and control package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-18-LH-01` | Valve Cv, Process Value, And Signal Scaling Package | `tag_register` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-18-LH-02` | Stormwater Or Treatment Telemetry Control Package | `process_value_basis` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-18-LH-03` | Protection And Control Setting Bridge To SLD | `valve_or_device_data` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-18-LH-04` | Commissioning And Calibration Review Packet | `signal_range` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-18-LH-05` | Chemical Dosing Flowmeter And Control Package | `control_mode` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-18-LH-06` | Fire Pump Pressure Signal And Alarm Package | `network_power` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-18-LH-07` | Valve Failure And Safe-State Repair Package | `commissioning_evidence` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-18-LH-08` | Instrumentation Source-Policy And Thin-Substrate Extension Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The control package should keep the same P&ID tags, process values, valve data, signal ranges, alarm limits, control actions, and protection settings across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

**Real-world fit**: SSC-18 matches ordinary instrument-loop design work: P&ID tag identity, valve sizing, signal range, control narrative, alarm/trip settings, and commissioning records have to agree before a loop can be handed to automation or operations. Public ISA routes support this split: ISA-5 covers documentation and illustration of measurement/control instruments and systems, ISA-75 covers control-valve design/testing/performance, and ISA-84 frames safety-instrumented lifecycle work. Sources: https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa5, https://www.isa.org/standards-and-publications/isa-standards/isa-75-standards, https://www.isa.org/standards-and-publications/isa-standards/isa-84-standards.

**Typical practitioner steps**: A practitioner starts from the P&ID and process basis, confirms loop/tag identity, checks valve service and Cv against the operating case, maps the process variable to a 4-20 mA range, verifies alarm/trip setpoints and fail state against the control narrative, then records the handoff in loop sheets, I/O lists, commissioning/calibration sheets, and a loop memo. The verifier should therefore check source identity, units, governing case, handoff values, and whether alarm/protection claims are source-supported.

**Software stack notes**: Current workflows are usually split across instrument selection/sizing tools, spreadsheet or vendor valve calculations, loop databases, PLC/SCADA engineering environments, and commissioning records. Siemens TIA Portal presents an integrated automation-engineering route from hardware configuration to commissioning, Rockwell Studio 5000/FactoryTalk covers Logix design and virtual commissioning routes, and Endress+Hauser publishes instrument-selection/application tooling around flow, level, pressure, temperature, analytics, and device data. Sources: https://www.siemens.com/en-us/products/tia-portal/, https://www.rockwellautomation.com/en-us/products/software/factorytalk/designsuite/studio-5000.html, https://www.endress.com/en/field-instruments-overview.

**Design implications**: The first hardening target should stay narrow: one task-owned valve/control loop with P&ID tag, valve datasheet, process basis, loop range, alarm setpoints, and commissioning record. Good variants should create P&ID-vs-datasheet conflicts, signal-range drift, alarm/trip margin failures, unsupported PLC/SCADA handoff changes, and overclaims of standards compliance or authority acceptance. Do not treat software/product pages as accepted project evidence or as a substitute for task-owned source files.

## Power Playground Skill-Derived Task Candidates

These candidates translate the local `Power-Playground-main` SME review skills into this SSC. They are design-note candidates only; they do not add runnable templates, accepted evidence, or source-pack hardening.

| Candidate Task | Source Skill | Source Pack Shape | What The Check Should Catch |
| --- | --- | --- | --- |
| Do the protection and control settings reconcile with the SLD and relay sheets? | `protection-study-review` | One-line, relay setting sheets, protection report, trip/control supply references, CT/VT data, and setting table. | Device tags, CT ratios, voltage bases, trip paths, or relay settings drift between the SLD, report, and setting sheets. |
| Are intertrips, alarms, and safe-state actions coherent enough for handoff? | `protection-study-review` plus `hv-power-system-review` | Protection functions, lockout/intertrip notes, alarm/trip setpoints, control narrative, SCADA/PLC handoff, and commissioning evidence. | A control action is claimed without source support, alarm/trip logic conflicts with protection settings, or the commissioning record does not prove the final handoff state. |

## Checks The Template Should Catch

These checks make `SSC-18` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `tag_register` source object or evidence artifact. | `ssc_18_source_identity_mismatch` |
| Scenario drift | One stage uses a different `process_value_basis` case without a case-selection record. | `ssc_18_scenario_mismatch` |
| Geometry or topology drift | `valve_or_device_data` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_18_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_18_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_18_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_18_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_18_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_18_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_18_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_18_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-18-LH-01` Valve Cv, Process Value, And Signal Scaling Package: start here because it uses the main instrumentation and control package source files and produces a source-pack-sized memo.
2. `SSC-18-LH-02` Stormwater Or Treatment Telemetry Control Package: add this after the first source pack has stable source files and control values.
3. `SSC-18-LH-03` Protection And Control Setting Bridge To SLD: add this after the first source pack has stable source files and control values.
4. `SSC-18-LH-04` Commissioning And Calibration Review Packet: add this after the first source pack has stable source files and control values.

The next source-pack artifact should be a `control_source_manifest.yaml` for one product, not another runtime path. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-18 product into a source pack.

A first executable-quality source pack for `SSC-18` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `control_source_manifest.yaml` | source fields such as `tag_register`, `process_value_basis`, `valve_or_device_data`, `signal_range`, `control_mode` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `control_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `control_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as instrumentation and control package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
