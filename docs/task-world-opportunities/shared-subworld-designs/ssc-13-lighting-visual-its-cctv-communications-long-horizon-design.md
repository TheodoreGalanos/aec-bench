# SSC-13 Lighting, visual performance, ITS, CCTV, and communications scene Long-Horizon Design

This document treats lighting, CCTV, ITS, and communications as one source-controlled operations package: scene geometry, device locations, lighting grid, message signs, cameras, network links, power, and storage assumptions have to line up. A useful long-horizon task keeps that operations basis consistent while moving between visibility, lux, CCTV, bandwidth, PoE, fibre, and message checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Visual and communications source state | road/room/field lighting grid, CCTV coverage, VMS/message library, topology and bandwidth/power |
| Memberships | 18 task-card memberships |
| Primary cards | 12 |
| Disciplines | electrical |
| Score | 23/30 |
| Candidate product | Visual operations package for road users, ITS, CCTV, lighting, and comms power |
| Main risk | Needs a concrete scene/layout, otherwise it is a loose collection of devices. |

The current card anchors cover lighting, visibility, ITS, CCTV, bandwidth, fibre, PoE, and communications checks:

| Card | Plain-language role |
| --- | --- |
| `bandwidth-calculation` | ITS network bandwidth capacity from device inventory. |
| `cctv-storage-calculation` | CCTV video storage sizing from bitrate and retention. |
| `conduit-fill-calculation` | Structured cabling conduit fill percentage. |
| `fiber-link-loss-budget` | Optical fibre link loss budget and power margin. |
| `interior-uniformity` | Calculates interior illuminance uniformity ratios. |
| `leni-calculation` | Calculates interior lighting LENI. |
| `lux-level-calculation` | Calculates average room illuminance using the lumen method. |
| `overlap-calculation` | Calculates rail signal overlap distance. |
| `poe-power-budget` | PoE switch power budget and headroom margin. |
| `ppm-calculation` | CCTV pixels-per-metre calculation from camera geometry. |

## Lighting And Communications Data Model

Treat each task as a check against the same lighting and communications package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-13`, the lighting and communications package source state is:

```text
S_ssc_13 = {
  scene_geometry,
  visual_targets,
  device_register,
  content_policy,
  network_topology,
  power_profile,
  operating_scenario,
  authority_partition,
}
```

The product combinations below share the same lighting and communications package data. A change to scene geometry, device location, lighting grid, sign, camera, network link, power supply, or storage assumption must carry through each check.

```text
W_ssc13_lh_01 x_S W_ssc13_lh_02
W_ssc13_lh_02 x_S W_ssc13_lh_03
W_ssc13_lh_03 x_S W_ssc13_lh_04
W_ssc13_lh_04 x_S W_ssc13_lh_05
W_ssc13_lh_05 x_S W_ssc13_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_13` | The lighting and communications package source state that all combined checks must agree on. |
| `W_ssc13_lh_01` | The first SSC-13 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same lighting and communications package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Lighting And Communications Source Manifest

Any `SSC-13` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `scene_geometry` | Road, room, field, platform, sign, camera, or luminaire geometry. | layout/lighting plan |
| `visual_targets` | Illuminance, luminance, PPM, uniformity, legibility, or message criteria. | criteria table |
| `device_register` | Luminaire, VMS, CCTV, PoE switch, radio/fibre, controller, and cabinet identities. | device schedule |
| `content_policy` | Message library, retention policy, recognition target, or display content. | operations policy |
| `network_topology` | Fibre, RF, conduit, PoE, bandwidth, and storage path. | network topology |
| `power_profile` | Installed power, PoE load, backup, dimming, and operating profile. | power schedule |
| `operating_scenario` | Day/night, incident, crowd, sport class, emergency, or outage mode. | operations note |
| `authority_partition` | Road, lighting, security, ITS, electrical, and privacy/owner criteria split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-13-LH-01: Road Visual Operations, ITS, CCTV, Lighting, And Comms Power Package

This is a lighting, ITS, CCTV, and communications work package for road visual operations, ITS, CCTV, lighting, and comms power. It starts with the road/field layout, lighting grid, and CCTV/VMS schedule.

The engineer checks lighting and visual target, CCTV/VMS device schedule, and bandwidth/PoE/power rollup. The output is the visual operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
road scene and operating mode
  -> lighting and visual target
  -> CCTV/VMS device schedule
  -> bandwidth/PoE/power rollup
  -> visual operations memo
```

Task-card anchors:

- `lux-level-calculation`
- `road-uniformity-check`
- `cctv-storage-calculation`
- `bandwidth-calculation`
- `poe-power-budget`

Source pack:

- road/field layout;
- lighting grid;
- CCTV/VMS schedule;
- network topology;
- cabinet power schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change road/field layout while keeping the downstream lighting and visual target fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make road/field layout disagree with lighting grid about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in CCTV/VMS schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on road scene and operating mode. The response should show lighting and visual target and CCTV/VMS device schedule, then record visual operations memo using the same source values throughout.

### SSC-13-LH-02: Station Or Building Security And Lighting Package

This is a lighting, ITS, CCTV, and communications work package for station or building security and lighting. It starts with the floor plan, occupancy schedule, and lighting layout.

The engineer checks lighting performance, CCTV/access-control coverage, and network/power consequence. The output is the security operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
floor/room scene and occupancy
  -> lighting performance
  -> CCTV/access-control coverage
  -> network/power consequence
  -> security operations memo
```

Task-card anchors:

- `lux-level-calculation`
- `interior-uniformity`
- `ppm-calculation`
- `access-controller-sizing`
- `poe-power-budget`

Source pack:

- floor plan;
- occupancy schedule;
- lighting layout;
- camera/access device schedule;
- network and power topology.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change floor plan while keeping the downstream lighting performance fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make floor plan disagree with occupancy schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in lighting layout only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on floor/room scene and occupancy. The response should show lighting performance and CCTV/access-control coverage, then record security operations memo using the same source values throughout.

### SSC-13-LH-03: Sports Or Field Lighting Power And Uniformity Package

This is a lighting, ITS, CCTV, and communications work package for sports or field lighting power and uniformity. It starts with the field layout, luminaire schedule, and calculation grid.

The engineer checks luminaire layout and uniformity, power/energy performance, and controls or operating mode. The output is the lighting memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
field geometry and lighting target
  -> luminaire layout and uniformity
  -> power/energy performance
  -> controls or operating mode
  -> lighting memo
```

Task-card anchors:

- `sports-illuminance-uniformity`
- `lux-level-calculation`
- `interior-uniformity`
- `leni-calculation`
- `voltage-drop`

Source pack:

- field layout;
- luminaire schedule;
- calculation grid;
- power schedule;
- operating profile.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change field layout while keeping the downstream luminaire layout and uniformity fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make field layout disagree with luminaire schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in calculation grid only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on field geometry and lighting target. The response should show luminaire layout and uniformity and power/energy performance, then record lighting memo using the same source values throughout.

### SSC-13-LH-04: Remote ITS Backup Communications Package

This is a lighting, ITS, CCTV, and communications work package for remote ITS backup communications. It starts with the device inventory, RF/fibre topology, and bandwidth table.

The engineer checks RF/fibre path and bandwidth, PoE/cabinet load, and battery autonomy. The output is the communications resilience memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
remote device inventory
  -> RF/fibre path and bandwidth
  -> PoE/cabinet load
  -> battery autonomy
  -> communications resilience memo
```

Task-card anchors:

- `rf-link-budget`
- `fiber-link-loss-budget`
- `bandwidth-calculation`
- `poe-power-budget`
- `battery-sizing`

Source pack:

- device inventory;
- RF/fibre topology;
- bandwidth table;
- PoE switch schedule;
- battery/solar data sheet.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change device inventory while keeping the downstream RF/fibre path and bandwidth fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make device inventory disagree with RF/fibre topology about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in bandwidth table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on remote device inventory. The response should show RF/fibre path and bandwidth and PoE/cabinet load, then record communications resilience memo using the same source values throughout.

### SSC-13-LH-05: VMS Message Library, Legibility, And Power Package

This is a lighting, ITS, CCTV, and communications work package for VMS message library, legibility, and power. It starts with the VMS schedule, message library, and road speed/geometry table.

The engineer checks viewing distance/speed, legibility and timing check, and power/network load. The output is the VMS operations memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
message library and sign identity
  -> viewing distance/speed
  -> legibility and timing check
  -> power/network load
  -> VMS operations memo
```

Task-card anchors:

- `vms-legibility-distance`
- `bandwidth-calculation`
- `power-load-calculation`
- `voltage-drop`
- `road-aeci-calculation`

Source pack:

- VMS schedule;
- message library;
- road speed/geometry table;
- network topology;
- power schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change VMS schedule while keeping the downstream viewing distance/speed fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make VMS schedule disagree with message library about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in road speed/geometry table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on message library and sign identity. The response should show viewing distance/speed and legibility and timing check, then record VMS operations memo using the same source values throughout.

### SSC-13-LH-06: CCTV Coverage, Pixel Density, And Storage Package

This is a lighting, ITS, CCTV, and communications work package for CCTV coverage, pixel density, and storage. It starts with the camera plan, scene/target list, and camera data sheet.

The engineer checks PPM/pixel density check, recording bitrate/storage, and network bandwidth and power. The output is the surveillance memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
camera layout and scene target
  -> PPM/pixel density check
  -> recording bitrate/storage
  -> network bandwidth and power
  -> surveillance memo
```

Task-card anchors:

- `ppm-calculation`
- `cctv-storage-calculation`
- `bandwidth-calculation`
- `poe-power-budget`
- `fiber-link-loss-budget`

Source pack:

- camera plan;
- scene/target list;
- camera data sheet;
- recording policy;
- network/power schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change camera plan while keeping the downstream PPM/pixel density check fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make camera plan disagree with scene/target list about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in camera data sheet only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on camera layout and scene target. The response should show PPM/pixel density check and recording bitrate/storage, then record surveillance memo using the same source values throughout.

### SSC-13-LH-07: Lighting Energy And Emergency Mode Package

This is a lighting, ITS, CCTV, and communications work package for lighting energy and emergency mode. It starts with the lighting layout, control schedule, and LENI/energy profile.

The engineer checks normal and emergency operating modes, LENI/energy check, and battery or generator load. The output is the lighting-energy memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
lighting grid and target
  -> normal and emergency operating modes
  -> LENI/energy check
  -> battery or generator load
  -> lighting-energy memo
```

Task-card anchors:

- `leni-calculation`
- `lux-level-calculation`
- `battery-sizing`
- `voltage-drop`
- `interior-uniformity`

Source pack:

- lighting layout;
- control schedule;
- LENI/energy profile;
- emergency load schedule;
- criteria table.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change lighting layout while keeping the downstream normal and emergency operating modes fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make lighting layout disagree with control schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in LENI/energy profile only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on lighting grid and target. The response should show normal and emergency operating modes and LENI/energy check, then record lighting-energy memo using the same source values throughout.

### SSC-13-LH-08: Visual Systems Review And Repair Package

This is a lighting, ITS, CCTV, and communications work package for visual systems review and repair. It starts with the layout, device schedule, and calculation grid.

The engineer checks review comment or changed scene, affected visual/network/power checks, and repair ledger. The output is the review response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
source pack and design output
  -> review comment or changed scene
  -> affected visual/network/power checks
  -> repair ledger
  -> review response
```

Task-card anchors:

- `lux-level-calculation`
- `cctv-storage-calculation`
- `bandwidth-calculation`
- `poe-power-budget`
- `vms-legibility-distance`

Source pack:

- layout;
- device schedule;
- calculation grid;
- comment register;
- criteria matrix.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change layout while keeping the downstream review comment or changed scene fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make layout disagree with device schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in calculation grid only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on design files and design output. The response should show review comment or changed scene and affected visual/network/power checks, then record review response using the same source values throughout.

## How The Variants Come Together

All `SSC-13` variants should use the same lighting and communications package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the lighting and communications package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-13-LH-01` | Road Visual Operations, ITS, CCTV, Lighting, And Comms Power Package | `scene_geometry` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-13-LH-02` | Station Or Building Security And Lighting Package | `visual_targets` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-13-LH-03` | Sports Or Field Lighting Power And Uniformity Package | `device_register` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-13-LH-04` | Remote ITS Backup Communications Package | `content_policy` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-13-LH-05` | VMS Message Library, Legibility, And Power Package | `network_topology` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-13-LH-06` | CCTV Coverage, Pixel Density, And Storage Package | `power_profile` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-13-LH-07` | Lighting Energy And Emergency Mode Package | `operating_scenario` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-13-LH-08` | Visual Systems Review And Repair Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The lighting and communications package should keep the same scene geometry, device locations, lighting grid, message signs, cameras, network links, power, and storage assumptions across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when the package is treated as one visual-operations scene, not as separate lighting, CCTV, VMS, and network calculations. Real projects keep the roadway, platform, room, field, or cabinet layout synchronized with luminaire grids, camera coverage, message-sign policies, fibre/RF topology, PoE loads, storage retention, and backup-power assumptions.
- The long-horizon behaviour appears when one scene change crosses discipline boundaries: moving a pole or cabinet can affect photometric grids, camera sightlines, VMS legibility, conduit/fibre length, switch power, UPS/battery autonomy, and commissioning records.
- The source-pack boundary should preserve evidence status. A lighting model, MUTCD or owner message policy, camera coverage plan, vendor datasheet, NTCIP device profile, and network topology are related but not interchangeable proof.

Typical practitioner steps:

1. Register scene geometry, lighting criteria, luminaire photometry, device schedule, sign/message library, camera target list, network topology, cabinet power, recording policy, and owner/authority criteria.
2. Run lighting calculations over the declared grid and operating case, then check visual targets, uniformity, glare/legibility, and documented result tables against the selected standard or owner criterion.
3. Lay out CCTV/VMS/ITS devices against the same scene, check PPM or DORI-style coverage, sign visibility and message constraints, bandwidth, fibre/RF loss, storage, PoE, and backup-power handoffs.
4. Issue a visual-operations or systems memo that names the controlling layout, device IDs, criteria, software outputs, handoff values, unresolved gaps, and reviewer or commissioning checks.

Software stack notes:

- [AGi32](https://lightinganalysts.com/agi32/) is a realistic lighting-calculation route for indoor and outdoor point-by-point illuminance/luminance, CAD-based geometry, photometric files, renderings, and calculation reports.
- [DIALux road lighting](https://www.dialux.com/en-GB/street-lighting) is a realistic route for road profiles, lighting classes, luminaire arrangements, EN 13201-style optimisation, evaluation fields, isolux charts, grid-point tables, and documentation exports.
- [FHWA's current MUTCD](https://mutcd.fhwa.dot.gov/kno_11th_Editionr1.htm) is the live route for U.S. traffic-control and changeable-message-sign rules; source packs should bind any extracted CMS or TTC rule to the current official PDF edition rather than a stale local excerpt.
- [AXIS Site Designer](https://www.axis.com/support/tools/axis-site-designer) and [JVSG IP Video System Design Tool](https://www.jvsg.com/ip-video-system-design-tool/) are realistic CCTV design routes for camera placement, coverage, pixel density, bandwidth, storage, power, bills of materials, and installation documentation.
- [ARC-IT](https://www.arc-it.net/) and the [NTCIP standards list](https://www.ntcip.org/document-numbers-and-status/) are realistic ITS architecture and device-communications routes, including dynamic message signs, CCTV camera control, electrical/lighting management systems, Ethernet/TCP-IP profiles, and project-specific communications views.

Design implications:

- Add `lighting_model_register`, `device_schedule`, `message_policy`, `camera_coverage_register`, `communications_profile`, `network_power_handoff`, `recording_retention_policy`, and `commissioning_comment_log` fields before hardening `SSC-13-LH-01`.
- Require luminaire IDs, photometric file references, grid/evaluation-field IDs, camera IDs, target zones, sign/message IDs, switch ports, PoE watts, bandwidth, storage, fibre/RF margins, and backup-power assumptions to survive through the operations memo.
- Negative cases should include a moved pole or cabinet that updates lighting but not CCTV/network handoffs, a stale MUTCD or owner message rule used as current, a camera target accepted without pixel-density evidence, and a PoE/storage value changed in the memo without source-table support.

## Checks The Template Should Catch

These checks make `SSC-13` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `scene_geometry` source object or evidence artifact. | `ssc_13_source_identity_mismatch` |
| Scenario drift | One stage uses a different `visual_targets` case without a case-selection record. | `ssc_13_scenario_mismatch` |
| Geometry or topology drift | `device_register` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_13_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_13_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_13_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_13_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_13_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_13_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_13_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_13_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-13-LH-01` Road Visual Operations, ITS, CCTV, Lighting, And Comms Power Package: start here because it uses the main lighting and communications package source files and produces a source-pack-sized memo.
2. `SSC-13-LH-02` Station Or Building Security And Lighting Package: add this after the first source pack has stable source files and control values.
3. `SSC-13-LH-03` Sports Or Field Lighting Power And Uniformity Package: add this after the first source pack has stable source files and control values.
4. `SSC-13-LH-04` Remote ITS Backup Communications Package: add this after the first source pack has stable source files and control values.

The next artifact after the package-contract example should be a source-pack parser/verifier that reads the task-owned SSC-13 files, recomputes oracle rows, checks negative cases, and scores the final memo without claiming project approval or benchmark readiness.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-13 product into a source pack.

The first task-owned seed for `SSC-13-LH-01` now exists at `real-world-grounding/lighting-visual-its-cctv-communications-package/road_visual_operations_source_pack/`. It is a runnable-synthetic seed with a closed road scene, task-owned source tables, handoff ledgers, expected output, verifier rules, negative cases, and a verifier implementation brief. It is also represented in the composite template catalogue as `road-visual-operations-package`, which materializes and verifies at package-contract level. It is not a full source-pack parser, not a generated benchmark instance, and not accepted project evidence.

A first executable-quality source pack for `SSC-13` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `lighting_comms_source_manifest.yaml` | source fields such as `scene_geometry`, `visual_targets`, `device_register`, `content_policy`, `network_topology` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `lighting_comms_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack formula-verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents and the package-contract example are intentionally bounded design artifacts, not benchmark-ready implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim source-pack parser implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: executable source-pack checks for the selected product, followed by richer variants and response scoring.
- They should be used as lighting and communications package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
