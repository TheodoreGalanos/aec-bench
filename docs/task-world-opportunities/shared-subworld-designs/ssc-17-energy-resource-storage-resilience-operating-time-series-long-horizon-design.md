# SSC-17 Energy resource, storage, resilience, and operating time-series world Long-Horizon Design

This document treats energy resilience as one source-controlled operating package: scenario, time index, resource profiles, load profiles, critical loads, energy assets, dispatch policy, and authority limits have to line up. A useful long-horizon task keeps that energy basis consistent while moving between PV, BESS, generator, biogas, feeder, outage, stormwater, fire, and commissioning checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Energy source state | solar/weather/load/gas/energy records, BESS/PV, biogas, critical load/autonomy, operating profile |
| Memberships | 62 task-card memberships |
| Primary cards | 13 |
| Disciplines | civil, electrical, mechanical, structural |
| Score | 27/30 |
| Candidate product | Energy resilience product joining PV/BESS, biogas, critical load, and feeder assumptions |
| Main risk | Strong but can duplicate PV-storage unless treatment/process or resilience surface is explicit. |

The current card anchors cover PV, BESS, battery, generator, biogas, critical-load, feeder, outage, and resilience checks:

| Card | Plain-language role |
| --- | --- |
| `culvert-capacity` | Culvert headwater analysis under inlet and outlet control using HDS-5 methodology. |
| `detention-volume-preliminary` | Preliminary detention volume estimate using simplified triangular hydrograph method. |
| `downpipe-sizing` | Size roof downpipes per AS/NZS 3500.3 using catchment area and rainfall intensity. |
| `flap-gate-headloss` | Flap gate headloss calculation for stormwater outfalls. |
| `freeboard-calculation` | Freeboard calculation for coastal/flood structures: total freeboard = wave_allowance + slr_allowance + construction_tolerance + safety_margin (NZS 4404 / MfE Guidance). |
| `gutter-sizing` | Size eaves gutters per AS/NZS 3500.3 using catchment area, rainfall intensity, and gutter grade. |
| `hgl-check` | Hydraulic grade line check for a single stormwater pipe reach. |
| `mannings-pipe-capacity` | Flow capacity and velocity in circular pipes using Manning's equation. |
| `open-channel-capacity` | Flow capacity and velocity in trapezoidal/rectangular open channels using Manning's equation. |
| `orifice-outlet-design` | Size orifice outlet to achieve target release rate from detention basin. |

## Energy Operating Data Model

Treat each task as a check against the same energy operating package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-17`, the energy operating package source state is:

```text
S_ssc_17 = {
  scenario_id,
  time_index,
  resource_profiles,
  load_profiles,
  critical_load_register,
  energy_asset_register,
  operating_policy,
  authority_partition,
}
```

The product combinations below share the same energy operating package data. A change to scenario, time index, resource profile, load profile, critical load, energy asset, dispatch policy, or authority limit must carry through each check.

```text
W_ssc17_lh_01 x_S W_ssc17_lh_02
W_ssc17_lh_02 x_S W_ssc17_lh_03
W_ssc17_lh_03 x_S W_ssc17_lh_04
W_ssc17_lh_04 x_S W_ssc17_lh_05
W_ssc17_lh_05 x_S W_ssc17_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_17` | The energy operating package source state that all combined checks must agree on. |
| `W_ssc17_lh_01` | The first SSC-17 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same energy operating package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Energy Source Manifest

Any `SSC-17` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `scenario_id` | Normal day, outage, storm, fire mode, heatwave, or process peak. | design basis |
| `time_index` | Interval/date basis used by resources, loads, dispatch, and autonomy. | load/weather file |
| `resource_profiles` | PV, grid, generator fuel, biogas, gas, or storage availability. | PVWatts/REopt/gas record |
| `load_profiles` | Electrical/thermal/process/fire/pumping/communications loads. | load schedule |
| `critical_load_register` | Loads that must survive the event and duration. | emergency power basis |
| `energy_asset_register` | PV, BESS, inverter, generator, feeder, fuel, and controls. | SLD/datasheets |
| `operating_policy` | Dispatch, export, load shedding, autonomy, generator start, non-export. | control narrative |
| `authority_partition` | Utility, electrical, process, fire, stormwater, and owner authority split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-17-LH-01: DER Resilience And Feeder Interconnection

This is a energy, storage, and resilience work package for der resilience and feeder interconnection. It starts with the PV resource/output table, load profile, and BESS/inverter datasheets.

The engineer checks BESS/generator dispatch and autonomy, feeder voltage/ampacity/export checks, and interconnection branch. The output is the commissioning memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
PV resource and load profile
  -> BESS/generator dispatch and autonomy
  -> feeder voltage/ampacity/export checks
  -> interconnection branch
  -> commissioning memo
```

Task-card anchors:

- `string-sizing`
- `dc-ac-ratio`
- `bess-sizing`
- `battery-sizing`
- `cable-ampacity`

Source pack:

- PV resource/output table;
- load profile;
- BESS/inverter datasheets;
- SLD and cable schedule;
- utility interconnection/export form.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change PV resource/output table while keeping the downstream BESS/generator dispatch and autonomy fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make PV resource/output table disagree with load profile about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in BESS/inverter datasheets only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on PV resource and load profile. The response should show BESS/generator dispatch and autonomy and feeder voltage/ampacity/export checks, then record commissioning memo using the same source values throughout.

### SSC-17-LH-02: Wastewater Energy Island

This is a energy, storage, and resilience work package for wastewater energy island. It starts with the influent/effluent sample table, PFD/process basis, and blower/motor schedule.

The engineer checks oxygen and blower load, sludge/biogas production, and energy dispatch. The output is the critical-process resilience memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
influent/process basis
  -> oxygen and blower load
  -> sludge/biogas production
  -> energy dispatch
  -> critical-process resilience memo
```

Task-card anchors:

- `mass-balance`
- `oxygen-requirements`
- `nitrification-srt`
- `biogas-production`
- `bess-sizing`

Source pack:

- influent/effluent sample table;
- PFD/process basis;
- blower/motor schedule;
- biogas/sludge record;
- PV/BESS/feeder schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change influent/effluent sample table while keeping the downstream oxygen and blower load fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make influent/effluent sample table disagree with PFD/process basis about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in blower/motor schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on influent/process basis. The response should show oxygen and blower load and sludge/biogas production, then record critical-process resilience memo using the same source values throughout.

### SSC-17-LH-03: Stormwater Controls And Pumping Outage Resilience

This is a energy, storage, and resilience work package for stormwater controls and pumping outage resilience. It starts with the SWMM-style files or rainfall table, drainage long section, and pump/control load list.

The engineer checks HGL or pump condition, controls/telemetry/pump load, and BESS/generator autonomy. The output is the control-failure memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
rainfall and storage/outlet state
  -> HGL or pump condition
  -> controls/telemetry/pump load
  -> BESS/generator autonomy
  -> control-failure memo
```

Task-card anchors:

- `detention-volume-preliminary`
- `hgl-check`
- `flap-gate-headloss`
- `battery-sizing`
- `voltage-drop`

Source pack:

- SWMM-style files or rainfall table;
- drainage long section;
- pump/control load list;
- backup supply datasheet;
- event window table.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change SWMM-style files or rainfall table while keeping the downstream HGL or pump condition fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make SWMM-style files or rainfall table disagree with drainage long section about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pump/control load list only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on rainfall and storage/outlet state. The response should show HGL or pump condition and controls/telemetry/pump load, then record control-failure memo using the same source values throughout.

### SSC-17-LH-04: BESS Fire, Containment, Ventilation, And Feeder

This is a energy, storage, and resilience work package for bess fire, containment, ventilation, and feeder. It starts with the BESS/inverter datasheets, SLD/cable schedule, and battery-room/container layout.

The engineer checks feeder/export basis, fire/ventilation/containment loads, and emergency mode. The output is the safety memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
BESS/inverter layout and energy capacity
  -> feeder/export basis
  -> fire/ventilation/containment loads
  -> emergency mode
  -> safety memo
```

Task-card anchors:

- `bess-sizing`
- `battery-sizing`
- `voltage-drop`
- `air-changes`
- `t-squared-hrr`

Source pack:

- BESS/inverter datasheets;
- SLD/cable schedule;
- battery-room/container layout;
- fire strategy;
- ventilation and containment schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change BESS/inverter datasheets while keeping the downstream feeder/export basis fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make BESS/inverter datasheets disagree with SLD/cable schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in battery-room/container layout only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on BESS/inverter layout and energy capacity. The response should show feeder/export basis and fire/ventilation/containment loads, then record safety memo using the same source values throughout.

### SSC-17-LH-05: Road And ITS Field Equipment Energy Resilience

This is a energy, storage, and resilience work package for road and ITS field equipment energy resilience. It starts with the road plan/profile, field device schedule, and network topology.

The engineer checks lighting/VMS/CCTV/comms load, cabinet backup/PV/BESS, and storm/outage event. The output is the operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
road corridor operating scene
  -> lighting/VMS/CCTV/comms load
  -> cabinet backup/PV/BESS
  -> storm/outage event
  -> operations memo
```

Task-card anchors:

- `road-aeci-calculation`
- `vms-legibility-distance`
- `poe-power-budget`
- `battery-sizing`
- `hgl-check`

Source pack:

- road plan/profile;
- field device schedule;
- network topology;
- cabinet load schedule;
- storm/flood exposure note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change road plan/profile while keeping the downstream lighting/VMS/CCTV/comms load fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make road plan/profile disagree with field device schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in network topology only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on road corridor operating scene. The response should show lighting/VMS/CCTV/comms load and cabinet backup/PV/BESS, then record operations memo using the same source values throughout.

### SSC-17-LH-06: Station Emergency Operations Energy Package

This is a energy, storage, and resilience work package for station emergency operations energy. It starts with the station plan, population schedule, and life-safety load schedule.

The engineer checks lift/escalator/fire/ventilation loads, storage/generator sizing, and feeder and load shed. The output is the emergency operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
population and emergency mode
  -> lift/escalator/fire/ventilation loads
  -> storage/generator sizing
  -> feeder and load shed
  -> emergency operations memo
```

Task-card anchors:

- `occupant-load`
- `egress-width`
- `air-changes`
- `nac-load-calculation`
- `battery-sizing`

Source pack:

- station plan;
- population schedule;
- life-safety load schedule;
- SLD/emergency power basis;
- load-shed sequence.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change station plan while keeping the downstream lift/escalator/fire/ventilation loads fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make station plan disagree with population schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in life-safety load schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on population and emergency mode. The response should show lift/escalator/fire/ventilation loads and storage/generator sizing, then record emergency operations memo using the same source values throughout.

### SSC-17-LH-07: Rail Corridor Weather, Electrical Capacity, And Backup Operations

This is a energy, storage, and resilience work package for rail corridor weather, electrical capacity, and backup operations. It starts with the route profile/span schedule, weather table, and signalling load schedule.

The engineer checks OLE or signal equipment load, backup supply and feeder margin, and degraded operation. The output is the rail resilience memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
weather and route profile
  -> OLE or signal equipment load
  -> backup supply and feeder margin
  -> degraded operation
  -> rail resilience memo
```

Task-card anchors:

- `single-span-sag-tension`
- `static-thermal-rating`
- `signal-sighting-distance`
- `warning-time-calculation`
- `battery-sizing`

Source pack:

- route profile/span schedule;
- weather table;
- signalling load schedule;
- feeder/OLE basis;
- operations rule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change route profile/span schedule while keeping the downstream OLE or signal equipment load fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make route profile/span schedule disagree with weather table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in signalling load schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on weather and route profile. The response should show OLE or signal equipment load and backup supply and feeder margin, then record rail resilience memo using the same source values throughout.

### SSC-17-LH-08: Coastal Or Marine Flood Energy Resilience

This is a energy, storage, and resilience work package for coastal or marine flood energy resilience. It starts with the tide/SLR/storm table, site section, and pump/outfall schedule.

The engineer checks pump/outfall/freeboard state, electrical equipment elevation, and backup energy. The output is the flood-resilience memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
coastal level and storm event
  -> pump/outfall/freeboard state
  -> electrical equipment elevation
  -> backup energy
  -> flood-resilience memo
```

Task-card anchors:

- `freeboard-calculation`
- `outfall-submergence-check`
- `pump-head-calculation`
- `battery-sizing`
- `voltage-drop`

Source pack:

- tide/SLR/storm table;
- site section;
- pump/outfall schedule;
- electrical equipment layout;
- backup source register.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change tide/SLR/storm table while keeping the downstream pump/outfall/freeboard state fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make tide/SLR/storm table disagree with site section about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in pump/outfall schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on coastal level and storm event. The response should show pump/outfall/freeboard state and electrical equipment elevation, then record flood-resilience memo using the same source values throughout.

## How The Variants Come Together

All `SSC-17` variants should use the same energy operating package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the energy operating package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-17-LH-01` | DER Resilience And Feeder Interconnection | `scenario_id` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-17-LH-02` | Wastewater Energy Island | `time_index` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-17-LH-03` | Stormwater Controls And Pumping Outage Resilience | `resource_profiles` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-17-LH-04` | BESS Fire, Containment, Ventilation, And Feeder | `load_profiles` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-17-LH-05` | Road And ITS Field Equipment Energy Resilience | `critical_load_register` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-17-LH-06` | Station Emergency Operations Energy Package | `energy_asset_register` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-17-LH-07` | Rail Corridor Weather, Electrical Capacity, And Backup Operations | `operating_policy` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-17-LH-08` | Coastal Or Marine Flood Energy Resilience | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The energy package should keep the same scenario, time index, resource profiles, load profiles, critical loads, energy assets, dispatch policy, and authority limits across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when a DER, storage, generator, or process-energy study has to keep the same weather/resource file, interval index, outage case, critical-load register, storage state, and feeder or interconnection boundary across several calculations.
- The long-horizon behaviour appears when the energy result has a non-electrical consequence: a stormwater pump fails during an outage, a treatment process loses aeration capacity, a rail or ITS asset enters degraded mode, or a BESS/fire/electrical package changes the operating envelope.
- The package should avoid becoming generic PV/BESS sizing. The source pack needs explicit scenario IDs, time-series provenance, load-shed policy, authority constraints, and a result ledger for autonomy, state of charge, export/import, and unmet load.

Typical practitioner steps:

1. Establish the design scenarios, interval resolution, weather/resource files, tariff or interconnection limits, critical and non-critical loads, asset options, storage/generator constraints, and operating policy.
2. Model generation, storage dispatch, autonomy, unmet load, export/import, and feeder or interconnection behaviour using the same interval and scenario basis.
3. Check the non-electrical consequence, such as pump operation, process aeration, field equipment uptime, emergency mode, or BESS safety boundary, against the energy result.
4. Issue a memo that ties source profiles, model version, scenario choice, load register, dispatch result, and authority constraints together.

Software stack notes:

- [NREL SAM](https://sam.nrel.gov/) is a realistic techno-economic modelling anchor for PV, battery storage, hybrid renewable systems, and financial cases.
- [SAM Battery Storage](https://sam.nrel.gov/battery-storage.html) is a realistic dispatch and storage anchor for behind-the-meter and front-of-meter battery cases.
- [SAM Hybrid Systems](https://sam.nrel.gov/hybrid-systems.html) is a realistic route for combined generation/storage scenarios before the package needs a feeder-specific source pack.
- [ETAP](https://etap.com/) is a realistic electrical digital-twin anchor for power-flow, protection, arc-flash, renewables/storage, distribution, and microgrid studies.

Design implications:

- Add `resource_profile_register`, `interval_load_register`, `dispatch_result_ledger`, and `interconnection_constraint_register` fields before hardening `SSC-17-LH-01` or `SSC-17-LH-03`.
- Require scenario ID, interval timestamps, critical-load IDs, and energy-asset IDs to survive across DER sizing, feeder checks, and resilience memo outputs.
- Negative cases should include time-index misalignment, swapped weather/resource files, critical-load drift, storage state reset, and an electrical memo that ignores the process or pump consequence.

## Checks The Template Should Catch

These checks make `SSC-17` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `scenario_id` source object or evidence artifact. | `ssc_17_source_identity_mismatch` |
| Scenario drift | One stage uses a different `time_index` case without a case-selection record. | `ssc_17_scenario_mismatch` |
| Geometry or topology drift | `resource_profiles` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_17_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_17_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_17_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_17_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_17_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_17_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_17_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_17_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-17-LH-01` DER Resilience And Feeder Interconnection: start here because it uses the main energy operating package source files and produces a source-pack-sized memo.
2. `SSC-17-LH-02` Wastewater Energy Island: add this after the first source pack has stable source files and control values.
3. `SSC-17-LH-03` Stormwater Controls And Pumping Outage Resilience: add this after the first source pack has stable source files and control values.
4. `SSC-17-LH-04` BESS Fire, Containment, Ventilation, And Feeder: add this after the first source pack has stable source files and control values.

The next artifact should be a `energy_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-17 product into a source pack.

A first executable-quality source pack for `SSC-17` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `energy_source_manifest.yaml` | source fields such as `scenario_id`, `time_index`, `resource_profiles`, `load_profiles`, `critical_load_register` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `energy_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `energy_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as energy operating package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
