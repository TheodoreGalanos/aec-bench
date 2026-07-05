# SSC-06 Equipment layout, motor schedule, and duty-point world Long-Horizon Design

This document treats equipment selection as one source-controlled package: equipment layout, duty point, curve, motor schedule, control mode, support condition, and power supply have to line up. A useful long-horizon task keeps that equipment basis consistent while moving between hydraulic duty, pump or blower selection, motor load, NPSH, support, controls, and energy checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Equipment source state | equipment layout, pump/blower/compressor/motor schedule, duty point, equipment datasheet/curve |
| Memberships | 64 task-card memberships |
| Primary cards | 11 |
| Disciplines | civil, electrical, mechanical, structural |
| Score | 27/30 |
| Candidate product | Pump/blower duty to electrical load, acoustic impact, support/foundation package |
| Main risk | Needs actual curve/datasheet or task-owned equipment schedule to avoid handwavey selection. |

The current card anchors cover pump, blower, motor, pipe, NPSH, power, support, and equipment-layout checks:

| Card | Plain-language role |
| --- | --- |
| `bund-volume-calculation` | Oil containment bund volume calculation per AS/NZS 1940. |
| `cerc-longshore-transport` | Longshore sediment transport rate using the CERC formula Q_l = K * (E*Cg)_b * sin(2*alpha_b) / (2 * (rho_s - rho_w) * g * (1 - p)). |
| `curve-elements` | Horizontal curve element calculation: tangent, arc, external distance, mid-ordinate, and PC/PT chainages. |
| `darcy-weisbach-headloss` | Friction head loss calculation using Darcy-Weisbach equation with Swamee-Jain friction factor. |
| `hazen-williams-headloss` | Friction head loss calculation using the Hazen-Williams empirical equation. |
| `hudson-armor-sizing` | Armor stone sizing using Hudson's equation W = rho_r * H^3 / (KD * (Sr-1)^3 * cot(alpha)). |
| `linear-wave-theory` | Linear (Airy) wave theory: wavelength, celerity, and group velocity via dispersion relation (USACE CEM). |
| `min-curve-radius` | Minimum horizontal curve radius using R = V^2 / (127 * (e_max + f)) per AGRD Part 3 §7. |
| `npsh-calculation` | Net Positive Suction Head Available calculation for pump station suction systems. |
| `pipe-velocity-check` | Pipe flow velocity compliance check against AS/NZS 3500.1 service-type limits. |

## Equipment Duty Data Model

Treat each task as a check against the same equipment duty package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-06`, the equipment duty package source state is:

```text
S_ssc_06 = {
  equipment_register,
  duty_point,
  layout_context,
  curve_family,
  motor_power,
  process_or_hydraulic_basis,
  impact_surfaces,
  authority_partition,
}
```

The product combinations below share the same equipment duty package data. A change to equipment layout, duty point, curve, motor schedule, control mode, support condition, or power supply must carry through each check.

```text
W_ssc06_lh_01 x_S W_ssc06_lh_02
W_ssc06_lh_02 x_S W_ssc06_lh_03
W_ssc06_lh_03 x_S W_ssc06_lh_04
W_ssc06_lh_04 x_S W_ssc06_lh_05
W_ssc06_lh_05 x_S W_ssc06_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_06` | The equipment duty package source state that all combined checks must agree on. |
| `W_ssc06_lh_01` | The first SSC-06 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same equipment duty package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Equipment Source Manifest

Any `SSC-06` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `equipment_register` | Pump, blower, compressor, fan, valve, or package equipment identity. | equipment schedule |
| `duty_point` | Flow, head, pressure, air demand, efficiency, speed, or operating point. | datasheet/curve |
| `layout_context` | Equipment location, suction/discharge, supports, receivers, and access. | layout/P&ID |
| `curve_family` | Manufacturer curve, performance envelope, NPSHr, power, or acoustic curve. | vendor data |
| `motor_power` | Motor input, starter, demand, feeder, and backup load state. | motor/electrical schedule |
| `process_or_hydraulic_basis` | Process oxygen, pump flow, pipe network, or compressed-air demand. | process basis/PFD |
| `impact_surfaces` | Noise, vibration, foundation, support, thrust, or maintenance constraints. | receiver/support plan |
| `authority_partition` | Mechanical, electrical, structural, acoustic, and owner criteria split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-06-LH-01: Pump Station Duty, Power, NPSH, And Feeder Package

This is a equipment layout and motor duty work package for pump station duty, power, npsh, and feeder. It starts with the wet-well schedule, rising-main long section, and pump curve or table.

The engineer checks rising-main losses, pump curve duty point, and power and NPSH check. The output is the selection memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
wet-well/site profile
  -> rising-main losses
  -> pump curve duty point
  -> power and NPSH check
  -> selection memo
```

Task-card anchors:

- `pump-head-calculation`
- `hazen-williams-friction`
- `minor-losses-calculation`
- `pump-power-efficiency`
- `npsh-available`

Source pack:

- wet-well schedule;
- rising-main long section;
- pump curve or table;
- motor/electrical schedule;
- operating level rule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change wet-well schedule while keeping the downstream rising-main losses fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make wet-well schedule disagree with rising-main long section about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pump curve or table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on wet-well/site profile. The response should show rising-main losses and pump curve duty point, then record selection memo using the same source values throughout.

### SSC-06-LH-02: Blower Process, Energy, And Acoustic Impact Package

This is a equipment layout and motor duty work package for blower process, energy, and acoustic impact. It starts with the influent/load basis, blower data sheet, and motor schedule.

The engineer checks blower duty and motor load, building or receiver layout, and noise attenuation check. The output is the process/acoustic memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
process oxygen demand
  -> blower duty and motor load
  -> building or receiver layout
  -> noise attenuation check
  -> process/acoustic memo
```

Task-card anchors:

- `oxygen-requirements`
- `pump-power-efficiency`
- `spl-log-sum`
- `distance-attenuation`
- `a-weighting`

Source pack:

- influent/load basis;
- blower data sheet;
- motor schedule;
- receiver plan;
- acoustic criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change influent/load basis while keeping the downstream blower duty and motor load fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make influent/load basis disagree with blower data sheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in motor schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on process oxygen demand. The response should show blower duty and motor load and building or receiver layout, then record process/acoustic memo using the same source values throughout.

### SSC-06-LH-03: Compressor Or Pneumatic System Package

This is a equipment layout and motor duty work package for compressor or pneumatic system. It starts with the air demand table, compressor data sheet, and receiver/storage schedule.

The engineer checks compressor capacity and duty, motor load and feeder check, and storage or pressure branch. The output is the compressed-air memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
air demand schedule
  -> compressor capacity and duty
  -> motor load and feeder check
  -> storage or pressure branch
  -> compressed-air memo
```

Task-card anchors:

- `air-demand`
- `pump-power-calculation`
- `power-load-calculation`
- `voltage-drop`
- `pressure-loss-calculation`

Source pack:

- air demand table;
- compressor data sheet;
- receiver/storage schedule;
- motor/electrical schedule;
- control narrative.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change air demand table while keeping the downstream compressor capacity and duty fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make air demand table disagree with compressor data sheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in receiver/storage schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on air demand schedule. The response should show compressor capacity and duty and motor load and feeder check, then record compressed-air memo using the same source values throughout.

### SSC-06-LH-04: Equipment Support, Foundation, And Vibration Package

This is a equipment layout and motor duty work package for equipment support, foundation, and vibration. It starts with the equipment layout, mass and support schedule, and foundation sketch.

The engineer checks support/foundation reaction, vibration isolation check, and structural load combination. The output is the installation memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
equipment layout and mass
  -> support/foundation reaction
  -> vibration isolation check
  -> structural load combination
  -> installation memo
```

Task-card anchors:

- `pipe-support-dead-load`
- `gravity-base-stability`
- `vibration-transmissibility`
- `load-combinations`
- `miner-fatigue`

Source pack:

- equipment layout;
- mass and support schedule;
- foundation sketch;
- vibration isolator data;
- load-case table.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change equipment layout while keeping the downstream support/foundation reaction fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make equipment layout disagree with mass and support schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in foundation sketch only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on equipment layout and mass. The response should show support/foundation reaction and vibration isolation check, then record installation memo using the same source values throughout.

### SSC-06-LH-05: Pump Affinity, Retrofit, And Energy-Performance Package

This is a equipment layout and motor duty work package for pump affinity, retrofit, and energy-performance. It starts with the existing pump curve, new operating scenario, and affinity-law worksheet.

The engineer checks speed or impeller change, new duty/power point, and NPSH and feeder consequence. The output is the retrofit recommendation. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
existing pump curve/duty
  -> speed or impeller change
  -> new duty/power point
  -> NPSH and feeder consequence
  -> retrofit recommendation
```

Task-card anchors:

- `pump-affinity-laws`
- `pump-power-efficiency`
- `npsh-available`
- `voltage-drop`
- `power-load-calculation`

Source pack:

- existing pump curve;
- new operating scenario;
- affinity-law worksheet;
- motor/drive data sheet;
- energy tariff or operating profile.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change existing pump curve while keeping the downstream speed or impeller change fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make existing pump curve disagree with new operating scenario about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in affinity-law worksheet only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on existing pump curve/duty. The response should show speed or impeller change and new duty/power point, then record retrofit recommendation using the same source values throughout.

### SSC-06-LH-06: Heat Exchanger Or Thermal Plant Equipment Package

This is a equipment layout and motor duty work package for heat exchanger or thermal plant equipment. It starts with the process flow/temperature table, heat-exchanger data sheet, and pump curve.

The engineer checks equipment sizing or LMTD check, pump/flow duty, and motor and support consequence. The output is the thermal equipment memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
process heat load
  -> equipment sizing or LMTD check
  -> pump/flow duty
  -> motor and support consequence
  -> thermal equipment memo
```

Task-card anchors:

- `lmtd-calculation`
- `mass-balance`
- `pump-head-calculation`
- `pump-power-calculation`
- `pipe-support-dead-load`

Source pack:

- process flow/temperature table;
- heat-exchanger data sheet;
- pump curve;
- motor schedule;
- support layout.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change process flow/temperature table while keeping the downstream equipment sizing or LMTD check fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make process flow/temperature table disagree with heat-exchanger data sheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pump curve only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on process heat load. The response should show equipment sizing or LMTD check and pump/flow duty, then record thermal equipment memo using the same source values throughout.

### SSC-06-LH-07: Marine Or Coastal Pumping Equipment Package

This is a equipment layout and motor duty work package for marine or coastal pumping equipment. It starts with the tide/tailwater table, pump station section, and pipe schedule.

The engineer checks pump duty and losses, power and generator check, and corrosion/product selection branch. The output is the coastal equipment memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
coastal/tidal boundary
  -> pump duty and losses
  -> power and generator check
  -> corrosion/product selection branch
  -> coastal equipment memo
```

Task-card anchors:

- `pump-head-calculation`
- `flap-gate-headloss`
- `pump-power-efficiency`
- `battery-sizing`
- `freeboard-calculation`

Source pack:

- tide/tailwater table;
- pump station section;
- pipe schedule;
- motor/load schedule;
- materials or corrosion note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change tide/tailwater table while keeping the downstream pump duty and losses fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make tide/tailwater table disagree with pump station section about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pipe schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on coastal/tidal boundary. The response should show pump duty and losses and power and generator check, then record coastal equipment memo using the same source values throughout.

### SSC-06-LH-08: Equipment Datasheet And Commissioning Review Package

This is a equipment layout and motor duty work package for equipment datasheet and commissioning review. It starts with the equipment schedule, manufacturer datasheet, and curve/table export.

The engineer checks datasheet limits and curve evidence, calculation trace, and commissioning or POR/AOR check. The output is the review response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
selected equipment schedule
  -> datasheet limits and curve evidence
  -> calculation trace
  -> commissioning or POR/AOR check
  -> review response
```

Task-card anchors:

- `por-aor-compliance`
- `pump-power-efficiency`
- `npsh-available`
- `gci-calculation`
- `velocity-check`

Source pack:

- equipment schedule;
- manufacturer datasheet;
- curve/table export;
- commissioning checklist;
- review comments.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change equipment schedule while keeping the downstream datasheet limits and curve evidence fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make equipment schedule disagree with manufacturer datasheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in curve/table export only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on selected equipment schedule. The response should show datasheet limits and curve evidence and calculation trace, then record review response using the same source values throughout.

## How The Variants Come Together

All `SSC-06` variants should use the same equipment duty package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the equipment duty package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-06-LH-01` | Pump Station Duty, Power, NPSH, And Feeder Package | `equipment_register` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-06-LH-02` | Blower Process, Energy, And Acoustic Impact Package | `duty_point` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-06-LH-03` | Compressor Or Pneumatic System Package | `layout_context` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-06-LH-04` | Equipment Support, Foundation, And Vibration Package | `curve_family` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-06-LH-05` | Pump Affinity, Retrofit, And Energy-Performance Package | `motor_power` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-06-LH-06` | Heat Exchanger Or Thermal Plant Equipment Package | `process_or_hydraulic_basis` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-06-LH-07` | Marine Or Coastal Pumping Equipment Package | `impact_surfaces` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-06-LH-08` | Equipment Datasheet And Commissioning Review Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The equipment package should keep the same equipment layout, duty point, curve, motor schedule, control mode, support condition, and power supply across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when pump, blower, compressor, or process equipment selection has to preserve the same duty point, curve family, equipment tag, motor/VFD schedule, layout constraint, and downstream power/support handoff.
- The long-horizon behaviour appears when one selected equipment point drives hydraulic performance, motor sizing, feeder load, NPSH margin, noise/vibration, support loads, commissioning checks, or a review response.
- The package should require actual datasheets, curve exports, or a task-owned equipment schedule. Otherwise it will drift into handwaved selection rather than a traceable duty-point workflow.

Typical practitioner steps:

1. Establish equipment tags, layout constraints, design flow/head or process duty, curve family, fluid properties, control mode, motor/VFD basis, and acceptance criteria.
2. Select or check equipment against system curves, operating cases, NPSH margin, efficiency, power, and manufacturer limits.
3. Pass selected duty and motor information to electrical, structural/support, acoustic, controls, and commissioning checks.
4. Issue a calculation or review package that ties equipment identity, curve source, selected duty point, handoff values, exceptions, and review comments together.

Software stack notes:

- [Datacor Fathom](https://www.datacor.com/products/fathom) is a realistic hydraulic modelling anchor for steady-state pipe-network pressure drop, flow distribution, scenarios, pump curves, NPSH evaluation, motor sizing, VFDs, and wire-to-water efficiency.
- [PIPE-FLO](https://www.pipe-flo.com/) is a realistic piping-system model and digital-twin anchor for design, operating, and lifecycle views of fluid systems.
- [EPA EPANET](https://www.epa.gov/water-research/epanet) is a realistic open modelling anchor for pressurized networks with pipes, pumps, valves, storage tanks, extended-period simulation, energy usage, and pump-operation studies.
- Vendor pump-selection or catalogue tools remain useful source routes when they can export the selected curve, efficiency, NPSHr, motor power, impeller/speed basis, and product identity.

Design implications:

- Add `equipment_curve_register`, `selected_duty_point`, `motor_vfd_schedule`, and `equipment_handoff_ledger` fields before hardening `SSC-06-LH-01`.
- Require equipment tag, curve revision, units, fluid properties, and control mode to survive across hydraulic, electrical, support, acoustic, and commissioning checks.
- Negative cases should include curve/source mismatch, duty-point unit drift, NPSH basis swap, motor schedule mismatch, and a review response that silently changes the selected equipment.

## Checks The Template Should Catch

These checks make `SSC-06` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `equipment_register` source object or evidence artifact. | `ssc_06_source_identity_mismatch` |
| Scenario drift | One stage uses a different `duty_point` case without a case-selection record. | `ssc_06_scenario_mismatch` |
| Geometry or topology drift | `layout_context` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_06_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_06_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_06_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_06_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_06_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_06_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_06_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_06_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-06-LH-01` Pump Station Duty, Power, NPSH, And Feeder Package: start here because it uses the main equipment duty package source files and produces a source-pack-sized memo.
2. `SSC-06-LH-02` Blower Process, Energy, And Acoustic Impact Package: add this after the first source pack has stable source files and control values.
3. `SSC-06-LH-03` Compressor Or Pneumatic System Package: add this after the first source pack has stable source files and control values.
4. `SSC-06-LH-04` Equipment Support, Foundation, And Vibration Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `equipment_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-06 product into a source pack.

A first executable-quality source pack for `SSC-06` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `equipment_source_manifest.yaml` | source fields such as `equipment_register`, `duty_point`, `layout_context`, `curve_family`, `motor_power` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `equipment_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `equipment_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as equipment duty package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
