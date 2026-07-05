# SSC-05 Electrical SLD, feeder, load, and protection world Long-Horizon Design

This document treats the electrical system as one source-controlled package: SLD, load schedule, cable routes, switchboard data, protection settings, fault level, and operating mode have to line up. A useful long-horizon task keeps that electrical basis consistent while moving between load, feeder, voltage, protection, arc-flash, backup-power, and equipment checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Electrical source state | single-line diagram, load schedule, feeder/cable identity, fault/protection basis, switchboard geometry |
| Memberships | 48 task-card memberships |
| Primary cards | 14 |
| Disciplines | electrical |
| Score | 26/30 |
| Candidate product | Feeder/SLD package for BESS, pump, fire, PoE, and arc-flash checks |
| Main risk | Many tasks are electrical-only unless a mechanical/civil equipment schedule is included. |

The current card anchors cover load, feeder, voltage drop, cable, protection, fault, battery, PoE, and equipment-power checks:

| Card | Plain-language role |
| --- | --- |
| `ac-resistance-temperature` | AC resistance of conductor at operating temperature including skin effect per IEC 60287. |
| `access-controller-sizing` | Size access controllers, power supplies, and backup battery capacity. |
| `all-red-interval-calculation` | Traffic signal all-red clearance interval. |
| `bandwidth-calculation` | ITS network bandwidth capacity from device inventory. |
| `battery-sizing` | Backup battery capacity and UPS apparent power sizing. |
| `bess-sizing` | Battery energy storage system sizing calculation per IEC 62933. |
| `bess-sizing-basic` | Calculates basic BESS power and energy capacity. |
| `busbar-forces` | Busbar short-circuit electromagnetic force and stress calculation per IEEE 605 / IEC 60865-1. |
| `cable-ampacity` | Cable ampacity derating calculation per AS/NZS 3008.1.1. |
| `car-dimensions-check` | Calculates lift car dimension margins. |

## Electrical System Data Model

Treat each task as a check against the same electrical distribution system source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-05`, the electrical distribution system source state is:

```text
S_ssc_05 = {
  sld_boundary,
  load_register,
  cable_and_route,
  fault_basis,
  protection_settings,
  equipment_handoff,
  operating_mode,
  authority_partition,
}
```

The product combinations below share the same electrical distribution system data. A change to SLD, load schedule, feeder, cable route, switchboard, fault level, protection setting, or operating mode must carry through each check.

```text
W_ssc05_lh_01 x_S W_ssc05_lh_02
W_ssc05_lh_02 x_S W_ssc05_lh_03
W_ssc05_lh_03 x_S W_ssc05_lh_04
W_ssc05_lh_04 x_S W_ssc05_lh_05
W_ssc05_lh_05 x_S W_ssc05_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_05` | The electrical distribution system source state that all combined checks must agree on. |
| `W_ssc05_lh_01` | The first SSC-05 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same electrical distribution system source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Electrical Source Manifest

Any `SSC-05` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `sld_boundary` | PCC, transformer, switchboard, feeder, load, and protection identities. | SLD |
| `load_register` | Connected, demand, future, critical, motor, fire, and process loads. | load schedule |
| `cable_and_route` | Cable size, material, length, installation, derating, and route membership. | cable schedule |
| `fault_basis` | Source fault level, impedance, transformer, and contribution assumptions. | fault study |
| `protection_settings` | Relay/fuse/breaker settings and clearing times. | protection curve/settings |
| `equipment_handoff` | Mechanical, fire, process, PV/BESS, PoE, or lighting equipment tied to the SLD. | equipment schedule |
| `operating_mode` | Normal, emergency, outage, non-export, fire, or maintenance state. | control/operation note |
| `authority_partition` | Code, utility, owner, fire, process, and manufacturer authorities. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-05-LH-01: Mechanical-Load To Feeder And Voltage Package

This is a electrical feeder and protection work package for mechanical-load to feeder and voltage. It starts with the mechanical equipment schedule, single-line diagram, and cable schedule.

The engineer checks SLD and feeder identity, voltage drop and ampacity check, and power factor or motor-start case. The output is the electrical design memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
equipment schedule and demand load
  -> SLD and feeder identity
  -> voltage drop and ampacity check
  -> power factor or motor-start case
  -> electrical design memo
```

Task-card anchors:

- `power-load-calculation`
- `voltage-drop`
- `radial-feeder-voltage-drop`
- `cable-ampacity`
- `pfc-sizing`

Source pack:

- mechanical equipment schedule;
- single-line diagram;
- cable schedule;
- load calculation table;
- owner voltage-drop criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change mechanical equipment schedule while keeping the downstream SLD and feeder identity fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make mechanical equipment schedule disagree with single-line diagram about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in cable schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on equipment schedule and demand load. The response should show SLD and feeder identity and voltage drop and ampacity check, then record electrical design memo using the same source values throughout.

### SSC-05-LH-02: PV/BESS Interconnection And Export-Control Package

This is a electrical feeder and protection work package for PV/bess interconnection and export-control. It starts with the PV module/inverter datasheets, BESS data sheet, and SLD and PCC definition.

The engineer checks string and inverter sizing, storage/autonomy basis, and feeder voltage/export check. The output is the interconnection memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
load and PV/BESS asset register
  -> string and inverter sizing
  -> storage/autonomy basis
  -> feeder voltage/export check
  -> interconnection memo
```

Task-card anchors:

- `string-sizing`
- `dc-ac-ratio`
- `bess-sizing`
- `battery-sizing`
- `voltage-drop-dc`

Source pack:

- PV module/inverter datasheets;
- BESS data sheet;
- SLD and PCC definition;
- load profile;
- utility export-control rule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change PV module/inverter datasheets while keeping the downstream string and inverter sizing fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make PV module/inverter datasheets disagree with BESS data sheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in SLD and PCC definition only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on load and PV/BESS asset register. The response should show string and inverter sizing and storage/autonomy basis, then record interconnection memo using the same source values throughout.

### SSC-05-LH-03: Switchboard Fault, Arc-Flash, And Earthing Package

This is a electrical feeder and protection work package for switchboard fault, arc-flash, and earthing. It starts with the single-line diagram, fault study table, and relay/protection setting sheet.

The engineer checks earthing/grid resistance input, protection clearing time, and incident energy and busbar force. The output is the safety note. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
SLD and fault level
  -> earthing/grid resistance input
  -> protection clearing time
  -> incident energy and busbar force
  -> safety note
```

Task-card anchors:

- `three-phase-fault-current`
- `grid-resistance`
- `incident-energy`
- `busbar-forces`
- `static-thermal-rating`

Source pack:

- single-line diagram;
- fault study table;
- relay/protection setting sheet;
- soil resistivity report;
- switchboard layout.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change single-line diagram while keeping the downstream earthing/grid resistance input fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make single-line diagram disagree with fault study table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in relay/protection setting sheet only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on SLD and fault level. The response should show earthing/grid resistance input and protection clearing time, then record safety note using the same source values throughout.

### SSC-05-LH-04: Fire/Life-Safety And Communications Load Package

This is a electrical feeder and protection work package for fire/life-safety and communications load. It starts with the fire alarm load schedule, access/CCTV device schedule, and communications topology.

The engineer checks NAC/access/CCTV/comms load, battery and feeder sizing, and emergency mode case. The output is the life-safety power memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
life-safety device register
  -> NAC/access/CCTV/comms load
  -> battery and feeder sizing
  -> emergency mode case
  -> life-safety power memo
```

Task-card anchors:

- `nac-load-calculation`
- `access-controller-sizing`
- `cctv-storage-calculation`
- `poe-power-budget`
- `battery-sizing`

Source pack:

- fire alarm load schedule;
- access/CCTV device schedule;
- communications topology;
- battery/UPS data sheet;
- emergency operating criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change fire alarm load schedule while keeping the downstream NAC/access/CCTV/comms load fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make fire alarm load schedule disagree with access/CCTV device schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in communications topology only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on life-safety device register. The response should show NAC/access/CCTV/comms load and battery and feeder sizing, then record life-safety power memo using the same source values throughout.

### SSC-05-LH-05: Pump Station MCC, Cable, And Protection Package

This is a electrical feeder and protection work package for pump station mcc, cable, and protection. It starts with the pump schedule, MCC single line, and cable schedule.

The engineer checks MCC or switchboard boundary, cable ampacity and voltage drop, and fault/protection basis. The output is the power design memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
pump/motor schedule
  -> MCC or switchboard boundary
  -> cable ampacity and voltage drop
  -> fault/protection basis
  -> power design memo
```

Task-card anchors:

- `pump-power-calculation`
- `power-load-calculation`
- `cable-ampacity`
- `voltage-drop`
- `three-phase-fault-current`

Source pack:

- pump schedule;
- MCC single line;
- cable schedule;
- protection setting table;
- pump duty/load basis.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change pump schedule while keeping the downstream MCC or switchboard boundary fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make pump schedule disagree with MCC single line about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in cable schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on pump/motor schedule. The response should show MCC or switchboard boundary and cable ampacity and voltage drop, then record power design memo using the same source values throughout.

### SSC-05-LH-06: PoE, Fibre, And Field Cabinet Power Package

This is a electrical feeder and protection work package for poe, fibre, and field cabinet power. It starts with the device schedule, network topology, and PoE switch schedule.

The engineer checks PoE load rollup, fibre/RF link budget, and UPS/battery autonomy. The output is the field cabinet memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
device topology
  -> PoE load rollup
  -> fibre/RF link budget
  -> UPS/battery autonomy
  -> field cabinet memo
```

Task-card anchors:

- `poe-power-budget`
- `fiber-link-loss-budget`
- `rf-link-budget`
- `battery-sizing`
- `voltage-drop`

Source pack:

- device schedule;
- network topology;
- PoE switch schedule;
- fibre/RF path table;
- battery or UPS data sheet.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change device schedule while keeping the downstream PoE load rollup fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make device schedule disagree with network topology about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in PoE switch schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on device topology. The response should show PoE load rollup and fibre/RF link budget, then record field cabinet memo using the same source values throughout.

### SSC-05-LH-07: Regional Load-Flow And Voltage-Regulation Review Package

This is a electrical feeder and protection work package for regional load-flow and voltage-regulation review. It starts with the SLD, load schedule, and feeder/cable schedule.

The engineer checks feeder voltage-drop calculation, voltage regulation or PFC check, and review criterion. The output is the response memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
SLD and load scenario
  -> feeder voltage-drop calculation
  -> voltage regulation or PFC check
  -> review criterion
  -> response memo
```

Task-card anchors:

- `radial-feeder-voltage-drop`
- `voltage-regulation`
- `pfc-sizing`
- `cable-ampacity`
- `power-load-calculation`

Source pack:

- SLD;
- load schedule;
- feeder/cable schedule;
- voltage criterion;
- review comments.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change SLD while keeping the downstream feeder voltage-drop calculation fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make SLD disagree with load schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in feeder/cable schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on SLD and load scenario. The response should show feeder voltage-drop calculation and voltage regulation or PFC check, then record response memo using the same source values throughout.

### SSC-05-LH-08: Electrical Source-Policy And Product Datasheet Package

This is a electrical feeder and protection work package for electrical source-policy and product datasheet. It starts with the product datasheet, certificate/listing record, and rating table.

The engineer checks rating/derating extraction, calculation consumption, and source-policy gate. The output is the submittal response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
datasheet/product identity
  -> rating/derating extraction
  -> calculation consumption
  -> source-policy gate
  -> submittal response
```

Task-card anchors:

- `cable-ampacity`
- `static-thermal-rating`
- `ac-resistance-temperature`
- `voltage-drop`
- `busbar-forces`

Source pack:

- product datasheet;
- certificate/listing record;
- rating table;
- calculation worksheet;
- submittal register.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change product datasheet while keeping the downstream rating/derating extraction fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make product datasheet disagree with certificate/listing record about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in rating table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on datasheet/product identity. The response should show rating/derating extraction and calculation consumption, then record submittal response using the same source values throughout.

## How The Variants Come Together

All `SSC-05` variants should use the same electrical distribution system workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the electrical distribution system package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-05-LH-01` | Mechanical-Load To Feeder And Voltage Package | `sld_boundary` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-05-LH-02` | PV/BESS Interconnection And Export-Control Package | `load_register` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-05-LH-03` | Switchboard Fault, Arc-Flash, And Earthing Package | `cable_and_route` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-05-LH-04` | Fire/Life-Safety And Communications Load Package | `fault_basis` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-05-LH-05` | Pump Station MCC, Cable, And Protection Package | `protection_settings` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-05-LH-06` | PoE, Fibre, And Field Cabinet Power Package | `equipment_handoff` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-05-LH-07` | Regional Load-Flow And Voltage-Regulation Review Package | `operating_mode` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-05-LH-08` | Electrical Source-Policy And Product Datasheet Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The electrical package should keep the same SLD, load schedule, feeder identities, cable routes, switchboard data, protection settings, fault level, and operating modes across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when a single-line diagram, load schedule, feeder/cable route, switchboard identity, fault basis, protection settings, and operating mode have to remain consistent across electrical calculations and discipline handoffs.
- The long-horizon behaviour appears when a mechanical pump, BESS/PV asset, fire/life-safety load, PoE/field cabinet, or process-equipment schedule changes feeder loading, voltage drop, short-circuit level, protection coordination, arc-flash result, or authority response.
- The package should keep the SLD and load schedule as controlled source objects. Electrical-only calculations are useful, but this cluster is strongest when equipment or civil/process loads enter as source-owned handoffs.

Typical practitioner steps:

1. Establish the SLD revision, switchboard and feeder IDs, load schedule, demand/diversity basis, cable routes, protective devices, fault-level source, earthing basis, and operating modes.
2. Run load flow, voltage drop, short-circuit, protection coordination, arc-flash, motor-starting, harmonics, or grounding checks as required by the package.
3. Reconcile mechanical/process/fire/communications equipment handoffs with feeder ratings, protection settings, cable data, switchboard duty, and operating constraints.
4. Issue a study package that ties SLD revision, load source, device settings, calculation outputs, labels or schedules, exceptions, and review responses together.

Software stack notes:

- [ETAP](https://etap.com/) is a realistic electrical-system lifecycle anchor for SLD-centred modelling, power flow, short circuit, protection, arc flash, renewables/storage, and distribution studies.
- [EasyPower](https://www.easypower.com/) is a realistic power-system analysis anchor for one-lines, short circuit, protection and coordination, arc flash, power flow, voltage drop, harmonics, grounding, and reports.
- [SKM PowerTools](https://www.skm.com/) is a realistic electrical analysis anchor for fault calculations, load flow, coordination, arc-flash hazards, motor starting, transient stability, grounding, and cable pulling.
- Open distribution-system simulators remain useful when feeder, DER, storage, or time-series behaviour needs to be checked, but the first package can stay on SLD, load, protection, and study-report source control until that detail is needed.

Design implications:

- Add `sld_revision_register`, `load_schedule_register`, `protective_device_register`, and `study_output_index` fields before hardening `SSC-05-LH-01`.
- Require feeder IDs, switchboard names, equipment tags, device settings, cable-route references, and operating mode to survive across load flow, short-circuit, protection, and review outputs.
- Negative cases should include stale SLD revision, load-schedule mismatch, wrong feeder identity, fault-level basis swap, protection-setting drift, and a downstream equipment memo that silently changes electrical loads.

## Power Playground Skill-Derived Task Candidates

These candidates translate the local `Power-Playground-main` SME review skills into this SSC. They are design-note candidates only; they do not add runnable templates, accepted evidence, or source-pack hardening.

| Candidate Task | Source Skill | Source Pack Shape | What The Check Should Catch |
| --- | --- | --- | --- |
| Is this HV single-line design ready for issue? | `hv-power-system-review` | SLD, load schedule, cable schedule, transformer/switchgear ratings, fault/load-flow extracts, and layout references. | SLD topology, equipment tags, voltage bases, load totals, feeder ratings, fault duty, operating modes, and study outputs disagree. |
| Will the relay settings trip the right device first? | `protection-study-review` | One-line, relay setting sheets, TCC-derived curve table, transformer data, cable data, motor data, CT ratios, and fault levels. | Protection curves use the wrong voltage base, CTI is too small, instantaneous pickup overreaches, cable or transformer damage curves are not protected, or report settings drift from relay sheets. |
| Is the switchroom electrical safety interface complete enough for design QA? | `hv-power-system-review` plus `substation-safe-design-assessment` | SLD, arc-flash/protection/earthing study references, switchroom GA object list, switching location, egress path, and visible safety interfaces. | Arc-flash, earthing, access, interlock, trip-supply, or emergency-egress assumptions are missing, inconsistent, or only assumed from a document that cannot prove them. |

## Checks The Template Should Catch

These checks make `SSC-05` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `sld_boundary` source object or evidence artifact. | `ssc_05_source_identity_mismatch` |
| Scenario drift | One stage uses a different `load_register` case without a case-selection record. | `ssc_05_scenario_mismatch` |
| Geometry or topology drift | `cable_and_route` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_05_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_05_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_05_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_05_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_05_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_05_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_05_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_05_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-05-LH-01` Mechanical-Load To Feeder And Voltage Package: start here because it uses the main electrical distribution system source files and produces a source-pack-sized memo.
2. `SSC-05-LH-02` PV/BESS Interconnection And Export-Control Package: add this after the first source pack has stable source files and control values.
3. `SSC-05-LH-03` Switchboard Fault, Arc-Flash, And Earthing Package: add this after the first source pack has stable source files and control values.
4. `SSC-05-LH-04` Fire/Life-Safety And Communications Load Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `electrical_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-05 product into a source pack.

A first executable-quality source pack for `SSC-05` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `electrical_source_manifest.yaml` | source fields such as `sld_boundary`, `load_register`, `cable_and_route`, `fault_basis`, `protection_settings` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `electrical_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `electrical_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as electrical distribution system product notes, while the source-pack build notes should be used only to guide later fixture packaging.
