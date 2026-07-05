# SSC-10 Process wastewater, treatment, and plant energy world Long-Horizon Design

This document treats the treatment process as one source-controlled plant package: influent load, tank volumes, aeration demand, sludge inventory, chemical dosing, biogas, energy use, and process controls have to line up. A useful long-horizon task keeps that process basis consistent while moving between mass balance, oxygen demand, equipment duty, power, controls, and energy-recovery checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Treatment source state | process basis, PFD, influent/effluent samples, basin schedules, aeration/sludge/biogas records |
| Memberships | 15 task-card memberships |
| Primary cards | 11 |
| Disciplines | civil, electrical, mechanical |
| Score | 27/30 |
| Candidate product | Wastewater energy island: process loads, biogas, PV/BESS, feeder |
| Main risk | Mostly process/mechanical until electrical load or energy schedule evidence is added. |

The current card anchors cover wastewater process, mass balance, aeration, sludge, chemical dosing, biogas, energy, and control checks:

| Card | Plain-language role |
| --- | --- |
| `pump-power-calc` | Pump power calculation for water/wastewater pump stations at a given duty point. |
| `4-20ma-scaling` | Linear process variable scaling to a 4-20 mA signal. |
| `biogas-production` | Biogas and methane production from volatile solids destruction. |
| `chemical-dosing` | Treatment chemical dose and feed rate calculation. |
| `cstr-volume` | Continuous stirred tank reactor volume calculation for first-order reactions. |
| `hrt-calculation` | Hydraulic retention time calculation for treatment units. |
| `mass-balance` | Global process mass balance closure check. |
| `mlss-inventory` | Mixed liquor suspended solids inventory calculation. |
| `nitrification-srt` | Required SRT for activated-sludge nitrification. |
| `oxygen-requirements` | Activated sludge oxygen demand calculation. |

## Treatment Process Data Model

Treat each task as a check against the same wastewater treatment package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-10`, the wastewater treatment package source state is:

```text
S_ssc_10 = {
  process_basis,
  process_flow_diagram,
  reactor_inventory,
  aeration_load,
  sludge_biogas,
  chemical_and_storage,
  control_instrumentation,
  authority_partition,
}
```

The product combinations below share the same wastewater treatment package data. A change to influent load, tank volume, aeration basis, sludge inventory, chemical dose, biogas rate, load profile, or control setting must carry through each check.

```text
W_ssc10_lh_01 x_S W_ssc10_lh_02
W_ssc10_lh_02 x_S W_ssc10_lh_03
W_ssc10_lh_03 x_S W_ssc10_lh_04
W_ssc10_lh_04 x_S W_ssc10_lh_05
W_ssc10_lh_05 x_S W_ssc10_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_10` | The wastewater treatment package source state that all combined checks must agree on. |
| `W_ssc10_lh_01` | The first SSC-10 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same wastewater treatment package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Treatment Source Manifest

Any `SSC-10` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `process_basis` | Influent, effluent, permit, flow, load, and temperature basis. | sampling table, permit |
| `process_flow_diagram` | Stream, basin, recycle, sludge, and chemical identities. | PFD/P&ID |
| `reactor_inventory` | Volume, MLSS, SRT, HRT, nitrification, and mass basis. | basin schedule |
| `aeration_load` | Oxygen demand, diffuser/blower duty, and motor load. | blower datasheet |
| `sludge_biogas` | Solids production, volatile solids destruction, gas, and energy yield. | digester/sludge record |
| `chemical_and_storage` | Chemical dosing, storage, bunding, and safety basis. | chemical schedule |
| `control_instrumentation` | Loop, valve, sensor, alarm, and SCADA identities. | loop schedule |
| `authority_partition` | Process permit, mechanical, electrical, environmental, and owner criteria split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-10-LH-01: Wastewater Energy Island

This is a process and wastewater treatment work package for wastewater energy island. It starts with the influent/effluent sample table, process basis/PFD, and blower/motor schedule.

The engineer checks oxygen and blower load, sludge/biogas production, and PV/BESS/feeder consequence. The output is the energy island memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
influent/process basis
  -> oxygen and blower load
  -> sludge/biogas production
  -> PV/BESS/feeder consequence
  -> energy island memo
```

Task-card anchors:

- `mass-balance`
- `oxygen-requirements`
- `nitrification-srt`
- `biogas-production`
- `bess-sizing`

Source pack:

- influent/effluent sample table;
- process basis/PFD;
- blower/motor schedule;
- biogas or sludge record;
- energy asset and feeder schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change influent/effluent sample table while keeping the downstream oxygen and blower load fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make influent/effluent sample table disagree with process basis/PFD about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in blower/motor schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on influent/process basis. The response should show oxygen and blower load and sludge/biogas production, then record energy island memo using the same source values throughout.

### SSC-10-LH-02: Aeration Blower Process, Power, And Acoustic Package

This is a process and wastewater treatment work package for aeration blower process, power, and acoustic. It starts with the sampling table, process criteria, and blower data sheet.

The engineer checks oxygen demand and blower duty, motor power, and receiver acoustic check. The output is the aeration/acoustic memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
organic/nitrification load
  -> oxygen demand and blower duty
  -> motor power
  -> receiver acoustic check
  -> aeration/acoustic memo
```

Task-card anchors:

- `oxygen-requirements`
- `nitrification-srt`
- `pump-power-efficiency`
- `spl-log-sum`
- `distance-attenuation`

Source pack:

- sampling table;
- process criteria;
- blower data sheet;
- motor schedule;
- receiver plan and acoustic criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change sampling table while keeping the downstream oxygen demand and blower duty fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make sampling table disagree with process criteria about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in blower data sheet only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on organic/nitrification load. The response should show oxygen demand and blower duty and motor power, then record aeration/acoustic memo using the same source values throughout.

### SSC-10-LH-03: Chemical Dosing, Storage, And Containment Package

This is a process and wastewater treatment work package for chemical dosing, storage, and containment. It starts with the process flow/load table, chemical dosing basis, and tank/storage schedule.

The engineer checks storage/refill basis, bund or containment volume, and pump/control load. The output is the chemical system memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
chemical dose and flow case
  -> storage/refill basis
  -> bund or containment volume
  -> pump/control load
  -> chemical system memo
```

Task-card anchors:

- `chemical-dosing`
- `bund-volume-calculation`
- `pump-power-calculation`
- `4-20ma-scaling`
- `voltage-drop`

Source pack:

- process flow/load table;
- chemical dosing basis;
- tank/storage schedule;
- bund detail;
- pump/control schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change process flow/load table while keeping the downstream storage/refill basis fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make process flow/load table disagree with chemical dosing basis about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in tank/storage schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on chemical dose and flow case. The response should show storage/refill basis and bund or containment volume, then record chemical system memo using the same source values throughout.

### SSC-10-LH-04: Instrumented Process Control And Valve Package

This is a process and wastewater treatment work package for instrumented process control and valve. It starts with the P&ID, loop schedule, and valve data sheet.

The engineer checks valve Cv or hydraulic duty, 4-20 mA scaling, and control/protection response. The output is the instrumentation memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
process variable and setpoint
  -> valve Cv or hydraulic duty
  -> 4-20 mA scaling
  -> control/protection response
  -> instrumentation memo
```

Task-card anchors:

- `cv-liquid-incompressible`
- `4-20ma-scaling`
- `mass-balance`
- `hrt-calculation`
- `pressure-loss-calculation`

Source pack:

- P&ID;
- loop schedule;
- valve data sheet;
- process range table;
- control narrative.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change P&ID while keeping the downstream valve Cv or hydraulic duty fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make P&ID disagree with loop schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in valve data sheet only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on process variable and setpoint. The response should show valve Cv or hydraulic duty and 4-20 mA scaling, then record instrumentation memo using the same source values throughout.

### SSC-10-LH-05: Clarifier Loading, Sludge, And Hydraulic Constraint Package

This is a process and wastewater treatment work package for clarifier loading, sludge, and hydraulic constraint. It starts with the clarifier schedule, sampling/load table, and sludge wasting table.

The engineer checks surface/solids loading, sludge production, and hydraulic residence or recycle effect. The output is the clarifier note. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
influent and clarifier basis
  -> surface/solids loading
  -> sludge production
  -> hydraulic residence or recycle effect
  -> clarifier note
```

Task-card anchors:

- `slr-calculation`
- `sor-calculation`
- `sludge-production`
- `hrt-calculation`
- `mass-balance`

Source pack:

- clarifier schedule;
- sampling/load table;
- sludge wasting table;
- hydraulic profile;
- permit or criteria table.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change clarifier schedule while keeping the downstream surface/solids loading fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make clarifier schedule disagree with sampling/load table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in sludge wasting table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on influent and clarifier basis. The response should show surface/solids loading and sludge production, then record clarifier note using the same source values throughout.

### SSC-10-LH-06: Wet-Weather Process And Bypass Resilience Package

This is a process and wastewater treatment work package for wet-weather process and bypass resilience. It starts with the wet-weather inflow table, process unit schedule, and pump/storage schedule.

The engineer checks reactor/clarifier capacity, pump or storage bottleneck, and energy/control consequence. The output is the wet-weather memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
wet-weather flow and load
  -> reactor/clarifier capacity
  -> pump or storage bottleneck
  -> energy/control consequence
  -> wet-weather memo
```

Task-card anchors:

- `hrt-calculation`
- `cstr-volume`
- `pump-power-calculation`
- `detention-volume-preliminary`
- `battery-sizing`

Source pack:

- wet-weather inflow table;
- process unit schedule;
- pump/storage schedule;
- control rules;
- permit criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change wet-weather inflow table while keeping the downstream reactor/clarifier capacity fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make wet-weather inflow table disagree with process unit schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pump/storage schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on wet-weather flow and load. The response should show reactor/clarifier capacity and pump or storage bottleneck, then record wet-weather memo using the same source values throughout.

### SSC-10-LH-07: Biogas, Sludge, And Generator Dispatch Package

This is a process and wastewater treatment work package for biogas, sludge, and generator dispatch. It starts with the sludge production table, digester/gas meter data, and generator data sheet.

The engineer checks biogas production, generator or boiler conversion, and critical process load. The output is the dispatch memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
sludge/volatile solids basis
  -> biogas production
  -> generator or boiler conversion
  -> critical process load
  -> dispatch memo
```

Task-card anchors:

- `sludge-production`
- `biogas-production`
- `mass-balance`
- `bess-sizing-basic`
- `power-load-calculation`

Source pack:

- sludge production table;
- digester/gas meter data;
- generator data sheet;
- load profile;
- operating policy.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change sludge production table while keeping the downstream biogas production fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make sludge production table disagree with digester/gas meter data about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in generator data sheet only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on sludge/volatile solids basis. The response should show biogas production and generator or boiler conversion, then record dispatch memo using the same source values throughout.

### SSC-10-LH-08: Treatment Review Response And Permit-Basis Package

This is a process and wastewater treatment work package for treatment review response and permit-basis. It starts with the permit criteria table, sampling dataset, and process calculation appendix.

The engineer checks source data and model branch, affected calculations, and comment response. The output is the compliance gap memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
permit/process criteria
  -> source data and model branch
  -> affected calculations
  -> comment response
  -> compliance gap memo
```

Task-card anchors:

- `nitrification-srt`
- `srt-calculation`
- `oxygen-requirements`
- `chemical-dosing`
- `sludge-production`

Source pack:

- permit criteria table;
- sampling dataset;
- process calculation appendix;
- comment register;
- authority matrix.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change permit criteria table while keeping the downstream source data and model branch fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make permit criteria table disagree with sampling dataset about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in process calculation appendix only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on permit/process criteria. The response should show source data and model branch and affected calculations, then record compliance gap memo using the same source values throughout.

## How The Variants Come Together

All `SSC-10` variants should use the same wastewater treatment package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the wastewater treatment package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-10-LH-01` | Wastewater Energy Island | `process_basis` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-10-LH-02` | Aeration Blower Process, Power, And Acoustic Package | `process_flow_diagram` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-10-LH-03` | Chemical Dosing, Storage, And Containment Package | `reactor_inventory` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-10-LH-04` | Instrumented Process Control And Valve Package | `aeration_load` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-10-LH-05` | Clarifier Loading, Sludge, And Hydraulic Constraint Package | `sludge_biogas` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-10-LH-06` | Wet-Weather Process And Bypass Resilience Package | `chemical_and_storage` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-10-LH-07` | Biogas, Sludge, And Generator Dispatch Package | `control_instrumentation` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-10-LH-08` | Treatment Review Response And Permit-Basis Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The treatment package should keep the same influent load, tank volumes, aeration demand, sludge inventory, dosing basis, biogas, energy use, and process controls across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when a wastewater process basis has to preserve the same influent/load dataset, permit criteria, tank and reactor inventory, aeration demand, sludge/biogas assumptions, chemical dosing basis, and energy schedule across process and plant-energy checks.
- The long-horizon behaviour appears when biological treatment calculations drive blower sizing, electrical load, acoustic impact, chemical storage, process controls, biogas dispatch, or a permit/reviewer response.
- The package should keep process performance and energy consequences tied together. A process-only SRT or oxygen calculation is useful, but it does not become this cluster until the same source basis reaches plant equipment, power, or operational response.

Typical practitioner steps:

1. Establish influent/effluent criteria, process flow diagram, sampling/load data, tank volumes, aeration/control strategy, sludge age/inventory, chemical dosing basis, and operating scenarios.
2. Build or check process calculations or a dynamic treatment model for SRT, oxygen demand, biological performance, sludge/biogas, and wet-weather or seasonal cases.
3. Pass aeration, blower, pump, chemical, generator, and control loads into equipment, electrical, acoustic, and energy-resilience checks.
4. Issue a process or compliance memo that ties permit criteria, source data, model branch, energy/load consequences, and reviewer comments together.

Software stack notes:

- [BioWin](https://envirosim.com/products/biowin) is a realistic wastewater process-simulation anchor for biological, chemical, and physical treatment process modelling.
- [GPS-X](https://www.hydromantis.com/GPS-X.html) is a realistic dynamic wastewater-treatment modelling anchor for plant design, operation, control, and optimization studies.
- [SUMO](https://www.dynamita.com/sumo/) is a realistic wastewater process-modelling anchor for treatment plant simulation, control, and resource-recovery scenarios.
- [EPA Energy Efficiency in Water and Wastewater Facilities](https://www.epa.gov/sustainable-water-infrastructure/energy-efficiency-water-and-wastewater-facilities) is a realistic public-practice route for connecting treatment assets, aeration, pumping, energy use, and improvement measures.

Design implications:

- Add `process_basis_register`, `influent_load_dataset`, `aeration_energy_ledger`, and `permit_criteria_register` fields before hardening `SSC-10-LH-01`.
- Require process case IDs, tank/reactor IDs, oxygen or aeration demand, sludge/biogas assumptions, and equipment loads to survive across process, energy, and review outputs.
- Negative cases should include process/model branch mismatch, stale influent dataset, aeration-load unit drift, permit-criteria swap, and an energy memo that ignores biological-process limits.

## Checks The Template Should Catch

These checks make `SSC-10` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `process_basis` source object or evidence artifact. | `ssc_10_source_identity_mismatch` |
| Scenario drift | One stage uses a different `process_flow_diagram` case without a case-selection record. | `ssc_10_scenario_mismatch` |
| Geometry or topology drift | `reactor_inventory` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_10_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_10_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_10_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_10_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_10_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_10_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_10_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_10_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-10-LH-01` Wastewater Energy Island: start here because it uses the main wastewater treatment package source files and produces a source-pack-sized memo.
2. `SSC-10-LH-02` Aeration Blower Process, Power, And Acoustic Package: add this after the first source pack has stable source files and control values.
3. `SSC-10-LH-03` Chemical Dosing, Storage, And Containment Package: add this after the first source pack has stable source files and control values.
4. `SSC-10-LH-04` Instrumented Process Control And Valve Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `treatment_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-10 product into a source pack.

A first executable-quality source pack for `SSC-10` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `treatment_source_manifest.yaml` | source fields such as `process_basis`, `process_flow_diagram`, `reactor_inventory`, `aeration_load`, `sludge_biogas` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `treatment_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `treatment_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as wastewater treatment package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
