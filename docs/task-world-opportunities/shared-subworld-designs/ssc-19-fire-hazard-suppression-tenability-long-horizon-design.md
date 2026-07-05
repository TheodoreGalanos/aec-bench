# SSC-19 Fire, hazard, suppression, and tenability world Long-Horizon Design

This document treats fire and hazard design as one source-controlled safety package: fire strategy, hazard inventory, water supply, sprinkler demand, ventilation, tenability, emergency power, and authority criteria have to line up. A useful long-horizon task keeps that safety basis consistent while moving between suppression, hydrant flow, fire-water storage, evacuation, visibility, heat, incident energy, and review checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Fire and hazard source state | fire strategy, sprinkler/hydrant/supply, design fire/visibility/steel temperature, hazardous inventory |
| Memberships | 11 task-card memberships |
| Primary cards | 8 |
| Disciplines | civil, electrical, mechanical |
| Score | 26/30 |
| Candidate product | BESS/fire/hazard package or fire-water/structural-fire/arc-flash safety product |
| Main risk | Standards and accepted calculation evidence are high-risk; public data may be sparse. |

The current card anchors cover fire-water, sprinkler, hydrant, tenability, visibility, heat release, emergency power, and hazard checks:

| Card | Plain-language role |
| --- | --- |
| `bund-volume-calculation` | Oil containment bund volume calculation per AS/NZS 1940. |
| `incident-energy` | Arc flash incident energy calculation per IEEE 1584 and NFPA 70E. |
| `available-flow-calculation` | Available fire flow from hydrant flow test. |
| `elevation-pressure` | Static pressure change from elevation difference. |
| `friction-loss-hazen-williams` | Imperial Hazen-Williams sprinkler pipe friction loss. |
| `nac-load-calculation` | Notification appliance circuit load and capacity check. |
| `sprinkler-discharge` | Sprinkler discharge calculation from K factor and pressure. |
| `steel-critical-temp` | Critical steel temperature calculation from structural-fire load ratio. |
| `t-squared-hrr` | T-squared fire growth heat release rate calculation. |
| `visibility-criterion` | Smoke visibility tenability criterion calculation. |

## Fire And Hazard Data Model

Treat each task as a check against the same fire and hazard package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-19`, the fire and hazard package source state is:

```text
S_ssc_19 = {
  hazard_inventory,
  fire_scenario,
  suppression_supply,
  tenability_state,
  life_safety_loads,
  structural_fire_state,
  review_packet,
  authority_partition,
}
```

The product combinations below share the same fire and hazard package data. A change to fire strategy, hazard inventory, water supply, sprinkler demand, ventilation case, tenability criterion, emergency supply, or authority criterion must carry through each check.

```text
W_ssc19_lh_01 x_S W_ssc19_lh_02
W_ssc19_lh_02 x_S W_ssc19_lh_03
W_ssc19_lh_03 x_S W_ssc19_lh_04
W_ssc19_lh_04 x_S W_ssc19_lh_05
W_ssc19_lh_05 x_S W_ssc19_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_19` | The fire and hazard package source state that all combined checks must agree on. |
| `W_ssc19_lh_01` | The first SSC-19 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same fire and hazard package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Fire And Hazard Source Manifest

Any `SSC-19` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `hazard_inventory` | Commodity, battery, chemical, fuel, occupancy, or storage arrangement. | hazard schedule |
| `fire_scenario` | Design fire, ignition, growth, storage height, fire mode, or incident case. | fire strategy |
| `suppression_supply` | Hydrant, sprinkler, water supply, pump, booster, and hydraulic basis. | fire calc/water form |
| `tenability_state` | Visibility, temperature, smoke, egress, and ventilation criteria. | tenability report |
| `life_safety_loads` | NAC, smoke control, emergency power, fire pumps, and critical loads. | load schedule |
| `structural_fire_state` | Steel temperature, fire rating, damage, or protection basis. | structural fire note |
| `review_packet` | AHJ/FM/insurer/property-risk review artifacts and comments. | review package |
| `authority_partition` | AHJ, fire code, FM/insurer, electrical, structural, mechanical, and owner authority split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-19-LH-01: Fire-Water, Sprinkler Demand, And Storage Hazard Package

This is a fire safety and hazard control work package for fire-water, sprinkler demand, and storage hazard. It starts with the hydrant test form, sprinkler layout/hazard table, and riser schematic.

The engineer checks hazard and sprinkler demand, friction/elevation losses, and pump or storage boost. The output is the fire-water memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
hydrant/supply curve
  -> hazard and sprinkler demand
  -> friction/elevation losses
  -> pump or storage boost
  -> fire-water memo
```

Task-card anchors:

- `available-flow-calculation`
- `water-supply-curve`
- `sprinkler-discharge`
- `friction-loss-hazen-williams`
- `elevation-pressure`

Source pack:

- hydrant test form;
- sprinkler layout/hazard table;
- riser schematic;
- pump curve;
- code/AHJ criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change hydrant test form while keeping the downstream hazard and sprinkler demand fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make hydrant test form disagree with sprinkler layout/hazard table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in riser schematic only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on hydrant/supply curve. The response should show hazard and sprinkler demand and friction/elevation losses, then record fire-water memo using the same source values throughout.

### SSC-19-LH-02: BESS Hazard, Containment, Ventilation, And Feeder Package

This is a fire safety and hazard control work package for bess hazard, containment, ventilation, and feeder. It starts with the BESS datasheet/layout, fire strategy, and ventilation schedule.

The engineer checks fire/hazard scenario, ventilation/visibility/containment check, and feeder and emergency load. The output is the safety memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
BESS layout and energy
  -> fire/hazard scenario
  -> ventilation/visibility/containment check
  -> feeder and emergency load
  -> safety memo
```

Task-card anchors:

- `bess-sizing`
- `t-squared-hrr`
- `air-changes`
- `visibility-criterion`
- `voltage-drop`

Source pack:

- BESS datasheet/layout;
- fire strategy;
- ventilation schedule;
- containment/drainage detail;
- SLD/load schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change BESS datasheet/layout while keeping the downstream fire/hazard scenario fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make BESS datasheet/layout disagree with fire strategy about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in ventilation schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on BESS layout and energy. The response should show fire/hazard scenario and ventilation/visibility/containment check, then record safety memo using the same source values throughout.

### SSC-19-LH-03: Structural Fire And Tenability Package

This is a fire safety and hazard control work package for structural fire and tenability. It starts with the fire strategy, HRR/design fire table, and structural member schedule.

The engineer checks steel critical temperature, visibility/tenability check, and egress or alarm consequence. The output is the fire engineering memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
design fire or HRR
  -> steel critical temperature
  -> visibility/tenability check
  -> egress or alarm consequence
  -> fire engineering memo
```

Task-card anchors:

- `t-squared-hrr`
- `steel-critical-temp`
- `visibility-criterion`
- `egress-width`
- `nac-load-calculation`

Source pack:

- fire strategy;
- HRR/design fire table;
- structural member schedule;
- tenability criterion;
- egress/alarm schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change fire strategy while keeping the downstream steel critical temperature fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make fire strategy disagree with HRR/design fire table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in structural member schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on design fire or HRR. The response should show steel critical temperature and visibility/tenability check, then record fire engineering memo using the same source values throughout.

### SSC-19-LH-04: Alarm, Smoke Control, And Emergency Power Package

This is a fire safety and hazard control work package for alarm, smoke control, and emergency power. It starts with the fire alarm zone plan, NAC load schedule, and smoke control/ventilation schedule.

The engineer checks NAC and smoke-control loads, battery/emergency power sizing, and fire mode branch. The output is the life-safety systems memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
zone/occupancy state
  -> NAC and smoke-control loads
  -> battery/emergency power sizing
  -> fire mode branch
  -> life-safety systems memo
```

Task-card anchors:

- `nac-load-calculation`
- `air-changes`
- `battery-sizing`
- `visibility-criterion`
- `occupant-load`

Source pack:

- fire alarm zone plan;
- NAC load schedule;
- smoke control/ventilation schedule;
- battery data sheet;
- emergency operations criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change fire alarm zone plan while keeping the downstream NAC and smoke-control loads fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make fire alarm zone plan disagree with NAC load schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in smoke control/ventilation schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on zone/occupancy state. The response should show NAC and smoke-control loads and battery/emergency power sizing, then record life-safety systems memo using the same source values throughout.

### SSC-19-LH-05: Warehouse Hazard, Storage Arrangement, And FM/AHJ Review Package

This is a fire safety and hazard control work package for warehouse hazard, storage arrangement, and fm/AHJ review. It starts with the storage layout, commodity/hazard table, and sprinkler design basis.

The engineer checks storage geometry, sprinkler demand or fire growth, and authority review branch. The output is the hazard response memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
commodity/hazard class
  -> storage geometry
  -> sprinkler demand or fire growth
  -> authority review branch
  -> hazard response memo
```

Task-card anchors:

- `sprinkler-discharge`
- `water-supply-curve`
- `t-squared-hrr`
- `visibility-criterion`
- `friction-loss-hazen-williams`

Source pack:

- storage layout;
- commodity/hazard table;
- sprinkler design basis;
- FM/AHJ review note;
- calculation appendix.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change storage layout while keeping the downstream storage geometry fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make storage layout disagree with commodity/hazard table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in sprinkler design basis only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on commodity/hazard class. The response should show storage geometry and sprinkler demand or fire growth, then record hazard response memo using the same source values throughout.

### SSC-19-LH-06: Fire Pump Fuel, Power, And Control Resilience Package

This is a fire safety and hazard control work package for fire pump fuel, power, and control resilience. It starts with the fire pump curve, motor/fuel data sheet, and controller load schedule.

The engineer checks motor/fuel/control load, backup or fuel autonomy, and pressure/flow consequence. The output is the fire pump resilience memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
fire pump duty
  -> motor/fuel/control load
  -> backup or fuel autonomy
  -> pressure/flow consequence
  -> fire pump resilience memo
```

Task-card anchors:

- `available-flow-calculation`
- `pump-power-efficiency`
- `battery-sizing`
- `water-supply-curve`
- `voltage-drop`

Source pack:

- fire pump curve;
- motor/fuel data sheet;
- controller load schedule;
- water supply curve;
- authority criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change fire pump curve while keeping the downstream motor/fuel/control load fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make fire pump curve disagree with motor/fuel data sheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in controller load schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on fire pump duty. The response should show motor/fuel/control load and backup or fuel autonomy, then record fire pump resilience memo using the same source values throughout.

### SSC-19-LH-07: Bund/Containment, Fire Water, And Environmental Isolation Package

This is a fire safety and hazard control work package for bund/containment, fire water, and environmental isolation. It starts with the inventory table, bund layout, and fire-water demand table.

The engineer checks bund/containment volume, fire-water/suppression case, and drainage isolation. The output is the containment memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
hazardous inventory
  -> bund/containment volume
  -> fire-water/suppression case
  -> drainage isolation
  -> containment memo
```

Task-card anchors:

- `bund-volume-calculation`
- `sprinkler-discharge`
- `t-squared-hrr`
- `flap-gate-headloss`
- `hgl-check`

Source pack:

- inventory table;
- bund layout;
- fire-water demand table;
- drainage isolation detail;
- environmental criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change inventory table while keeping the downstream bund/containment volume fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make inventory table disagree with bund layout about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in fire-water demand table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on hazardous inventory. The response should show bund/containment volume and fire-water/suppression case, then record containment memo using the same source values throughout.

### SSC-19-LH-08: Fire Review Response And Evidence Boundary Package

This is a fire safety and hazard control work package for fire review response and evidence boundary. It starts with the source index, review comments, and hazard table.

The engineer checks review comment or hazard change, affected hydraulic/tenability/electrical checks, and unresolved evidence gap. The output is the response memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
fire source pack and authority basis
  -> review comment or hazard change
  -> affected hydraulic/tenability/electrical checks
  -> unresolved evidence gap
  -> response memo
```

Task-card anchors:

- `available-flow-calculation`
- `sprinkler-discharge`
- `visibility-criterion`
- `incident-energy`
- `battery-sizing`

Source pack:

- source index;
- review comments;
- hazard table;
- calculation excerpts;
- AHJ/FM/code-support source references.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change source index while keeping the downstream review comment or hazard change fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make source index disagree with review comments about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in hazard table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on fire design files and authority basis. The response should show review comment or hazard change and affected hydraulic/tenability/electrical checks, then record response memo using the same source values throughout.

## How The Variants Come Together

All `SSC-19` variants should use the same fire and hazard package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the fire and hazard package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-19-LH-01` | Fire-Water, Sprinkler Demand, And Storage Hazard Package | `hazard_inventory` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-19-LH-02` | BESS Hazard, Containment, Ventilation, And Feeder Package | `fire_scenario` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-19-LH-03` | Structural Fire And Tenability Package | `suppression_supply` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-19-LH-04` | Alarm, Smoke Control, And Emergency Power Package | `tenability_state` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-19-LH-05` | Warehouse Hazard, Storage Arrangement, And FM/AHJ Review Package | `life_safety_loads` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-19-LH-06` | Fire Pump Fuel, Power, And Control Resilience Package | `structural_fire_state` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-19-LH-07` | Bund/Containment, Fire Water, And Environmental Isolation Package | `review_packet` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-19-LH-08` | Fire Review Response And Evidence Boundary Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The fire and hazard package should keep the same fire strategy, hazard inventory, water supply, sprinkler demand, ventilation, tenability, emergency power, and authority criteria across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when the package is treated as a fire-protection design and authority-review bundle, not as one hydraulic or tenability calculation. Real projects keep hazard classification, storage arrangement, fire-water source, sprinkler demand, smoke-control or tenability assumptions, emergency power, and AHJ/FM/insurer review comments tied to the same declared scenario.
- The BESS and warehouse variants are plausible only when the hazard inventory and operating mode are explicit. A battery-room, warehouse-rack, public-building, and pump-room case may all touch fire water and emergency power, but their design-fire, suppression, ventilation, monitoring, and review gates are not interchangeable.
- The current product list makes sense. The main tightening is to require a fire strategy or hazard-basis memo before water-supply, tenability, alarm, emergency-power, and authority-response checks can reuse values.

Typical practitioner steps:

1. Establish occupancy, hazard classification, storage or equipment inventory, fire scenario, applicable authority basis, and review roles.
2. Assemble water-supply, sprinkler, pump, alarm, smoke-control, ventilation, emergency-power, and containment source records.
3. Run the product-specific checks: fire-flow/sprinkler demand, pump/storage adequacy, BESS or storage-hazard criteria, smoke/tenability interaction, emergency load support, and review-comment response.
4. Issue a memo that names the governing fire scenario, selected criteria, controlling water/power/tenability margins, unresolved authority assumptions, and source evidence used.

Software stack notes:

- [FDS and Smokeview](https://pages.nist.gov/fds-smv/) are realistic fire and smoke modelling anchors where the package needs scenario, heat-release, smoke, detector, sprinkler-activation, or tenability evidence rather than only code-table checks.
- [FM property loss prevention data sheets](https://www.fm.com/resources/fm-data-sheets) are a realistic property-risk review anchor for warehouse, industrial, pump, storage, and fire-protection recommendations; use them as an authority family unless a specific data sheet is captured.
- [EPANET](https://www.epa.gov/water-research/epanet) and [WNTR](https://usepa.github.io/WNTR/) are realistic open water-supply modelling anchors for hydrant/fire-flow network checks, while sprinkler-code compliance and AHJ approval remain separate evidence surfaces.
- [NFPA 13](https://www.nfpa.org/codes-and-standards/nfpa-13-standard-development/13) and [NFPA 855](https://www.nfpa.org/codes-and-standards/nfpa-855-standard-development/855) are useful standards routes for sprinkler and energy-storage fire-safety branches, but source packs still need accessible clauses, project criteria, or task-owned excerpts before deterministic grading.

Design implications:

- Add `fire_strategy_memo`, `hazard_inventory`, `design_fire_scenario`, `water_supply_basis`, `suppression_demand_basis`, and `authority_review_packet` fields before hardening `SSC-19-LH-01` or `SSC-19-LH-02`.
- Keep AHJ, insurer/FM, owner, manufacturer, and discipline criteria as separate review roles rather than one generic approval flag.
- Negative cases should include reused water-flow data with a different hazard class, a BESS memo that ignores ventilation or emergency power, and a tenability output that silently changes the design-fire scenario.

## Power Playground Skill-Derived Task Candidates

These candidates translate the local `Power-Playground-main` SME review skills into this SSC. They are design-note candidates only; they do not add runnable templates, accepted evidence, or source-pack hardening.

| Candidate Task | Source Skill | Source Pack Shape | What The Check Should Catch |
| --- | --- | --- | --- |
| Could a transformer fire or battery event block escape or emergency response? | `substation-safe-design-assessment` | GA object list, transformer or battery-room location, doors, egress path, fire barriers, ventilation notes, and visible emergency-response provisions. | The fire or gas hazard affects egress, emergency access, or occupied rooms, but the response treats separation, ventilation, or response provisions as proven without evidence. |
| Are fire detection, suppression, and oil containment visible or only assumed? | `substation-safe-design-assessment` plus `hv-power-system-review` | Fire detection/suppression references, bunding or drainage objects, transformer data, battery-room notes, emergency power/load references, and verification log. | Detection, suppression, containment, ventilation, or emergency-power assumptions are missing from the drawing/source packet or not separated into verification items. |

## Checks The Template Should Catch

These checks make `SSC-19` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `hazard_inventory` source object or evidence artifact. | `ssc_19_source_identity_mismatch` |
| Scenario drift | One stage uses a different `fire_scenario` case without a case-selection record. | `ssc_19_scenario_mismatch` |
| Geometry or topology drift | `suppression_supply` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_19_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_19_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_19_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_19_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_19_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_19_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_19_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_19_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-19-LH-01` Fire-Water, Sprinkler Demand, And Storage Hazard Package: start here because it uses the main fire and hazard package source files and produces a source-pack-sized memo.
2. `SSC-19-LH-02` BESS Hazard, Containment, Ventilation, And Feeder Package: add this after the first source pack has stable source files and control values.
3. `SSC-19-LH-03` Structural Fire And Tenability Package: add this after the first source pack has stable source files and control values.
4. `SSC-19-LH-04` Alarm, Smoke Control, And Emergency Power Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `fire_hazard_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-19 product into a source pack.

A first executable-quality source pack for `SSC-19` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `fire_hazard_source_manifest.yaml` | source fields such as `hazard_inventory`, `fire_scenario`, `suppression_supply`, `tenability_state`, `life_safety_loads` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `fire_hazard_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `fire_hazard_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as fire and hazard package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
