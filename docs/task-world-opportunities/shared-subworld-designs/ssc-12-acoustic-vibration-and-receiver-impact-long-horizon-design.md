# SSC-12 Acoustic, vibration, and receiver-impact world Long-Horizon Design

This document treats acoustic and vibration assessment as one source-controlled receiver package: equipment noise, operating case, receiver location, spectra, attenuation path, room response, mitigation, and criteria have to line up. A useful long-horizon task keeps that acoustic basis consistent while moving between equipment duty, noise, vibration, receiver impact, mitigation, and compliance checks.

## Evidence Basis

| Field | Value |
| --- | --- |
| Acoustic source state | equipment noise/vibration schedule, source map, receiver plan, octave spectra, operating scenario |
| Memberships | 6 task-card memberships |
| Primary cards | 6 |
| Disciplines | mechanical |
| Score | 19/30 |
| Candidate product | Equipment power/duty to acoustic/vibration receiver impact package |
| Main risk | Small current card substrate unless joined to equipment and site layout clusters. |

The current card anchors cover noise, vibration, room acoustics, receiver distance, spectra, fatigue, isolation, and mitigation checks:

| Card | Plain-language role |
| --- | --- |
| `a-weighting` | A-weighted octave-band sound level calculation. |
| `distance-attenuation` | Point-source sound pressure level adjustment for a change in distance. |
| `miner-fatigue` | Cumulative fatigue damage calculation using Miner's rule. |
| `sabine-rt60` | Single-band reverberation time calculation using Sabine formula. |
| `spl-log-sum` | Three-source sound pressure level logarithmic summation. |
| `vibration-transmissibility` | Damped vibration transmissibility calculation. |

## Acoustic Receiver Data Model

Treat each task as a check against the same acoustic receiver package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-12`, the acoustic receiver package source state is:

```text
S_ssc_12 = {
  source_register,
  receiver_plan,
  operating_scenario,
  spectral_basis,
  mitigation_state,
  structural_path,
  criteria_targets,
  authority_partition,
}
```

The product combinations below share the same acoustic receiver package data. A change to equipment source, operating case, receiver location, octave spectrum, attenuation path, room response, mitigation, or criteria must carry through each check.

```text
W_ssc12_lh_01 x_S W_ssc12_lh_02
W_ssc12_lh_02 x_S W_ssc12_lh_03
W_ssc12_lh_03 x_S W_ssc12_lh_04
W_ssc12_lh_04 x_S W_ssc12_lh_05
W_ssc12_lh_05 x_S W_ssc12_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_12` | The acoustic receiver package source state that all combined checks must agree on. |
| `W_ssc12_lh_01` | The first SSC-12 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same acoustic receiver package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Acoustic Source Manifest

Any `SSC-12` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `source_register` | Equipment/source identity, operating point, sound power, vibration, or spectrum. | equipment/acoustic schedule |
| `receiver_plan` | Sensitive receivers, distances, rooms, boundaries, and paths. | site/room plan |
| `operating_scenario` | Normal, peak, night, emergency, construction, or degraded operating mode. | operations note |
| `spectral_basis` | Octave bands, A-weighting, attenuation, transmissibility, and summation basis. | acoustic data |
| `mitigation_state` | Enclosure, barrier, isolation, mounting, damping, or operational control. | mitigation drawing |
| `structural_path` | Mounting, supports, fatigue path, slab/structure, and dynamic state. | structural/support note |
| `criteria_targets` | Noise, vibration, fatigue, reverberation, or comfort limits. | criteria/permit |
| `authority_partition` | Mechanical, acoustic, structural, environmental, and owner authority split. | criteria matrix |

## Candidate Long-Horizon Products

### SSC-12-LH-01: Blower Or Pump Duty To Acoustic Impact Package

This is a acoustic and vibration work package for blower or pump duty to acoustic impact. It starts with the equipment schedule, octave spectrum/source data, and site/receiver plan.

The engineer checks sound power or octave spectrum, receiver distance and shielding, and combined noise and A-weighting. The output is the impact memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
equipment duty point and operating mode
  -> sound power or octave spectrum
  -> receiver distance and shielding
  -> combined noise and A-weighting
  -> impact memo
```

Task-card anchors:

- `a-weighting`
- `spl-log-sum`
- `distance-attenuation`
- `pump-power-efficiency`
- `oxygen-requirements`

Source pack:

- equipment schedule;
- octave spectrum/source data;
- site/receiver plan;
- operating scenario;
- noise criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change equipment schedule while keeping the downstream sound power or octave spectrum fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make equipment schedule disagree with octave spectrum/source data about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in site/receiver plan only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on equipment duty point and operating mode. The response should show sound power or octave spectrum and receiver distance and shielding, then record impact memo using the same source values throughout.

### SSC-12-LH-02: Vibration Isolation And Support Package

This is a acoustic and vibration work package for vibration isolation and support. It starts with the equipment data sheet, support layout, and isolator data.

The engineer checks vibration transmissibility, support/foundation check, and fatigue or serviceability consequence. The output is the isolation memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
equipment mass/speed and support layout
  -> vibration transmissibility
  -> support/foundation check
  -> fatigue or serviceability consequence
  -> isolation memo
```

Task-card anchors:

- `vibration-transmissibility`
- `miner-fatigue`
- `pipe-support-dead-load`
- `gravity-base-stability`
- `pump-power-calculation`

Source pack:

- equipment data sheet;
- support layout;
- isolator data;
- foundation/support schedule;
- vibration criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change equipment data sheet while keeping the downstream vibration transmissibility fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make equipment data sheet disagree with support layout about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in isolator data only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on equipment mass/speed and support layout. The response should show vibration transmissibility and support/foundation check, then record isolation memo using the same source values throughout.

### SSC-12-LH-03: Room Acoustic And HVAC Operations Package

This is a acoustic and vibration work package for room acoustic and HVAC operations. It starts with the room plan/volume, finish schedule, and HVAC/equipment schedule.

The engineer checks RT60 or absorption check, HVAC/equipment noise source, and occupancy or operating mode. The output is the room acoustic memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
room geometry and finishes
  -> RT60 or absorption check
  -> HVAC/equipment noise source
  -> occupancy or operating mode
  -> room acoustic memo
```

Task-card anchors:

- `sabine-rt60`
- `spl-log-sum`
- `a-weighting`
- `air-changes`
- `occupant-load`

Source pack:

- room plan/volume;
- finish schedule;
- HVAC/equipment schedule;
- occupancy scenario;
- acoustic criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change room plan/volume while keeping the downstream RT60 or absorption check fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make room plan/volume disagree with finish schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in HVAC/equipment schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on room geometry and finishes. The response should show RT60 or absorption check and HVAC/equipment noise source, then record room acoustic memo using the same source values throughout.

### SSC-12-LH-04: Construction Noise And Vibration Monitoring Package

This is a acoustic and vibration work package for construction noise and vibration monitoring. It starts with the construction staging plan, equipment/source schedule, and receiver map.

The engineer checks source power/vibration level, receiver and distance map, and monitoring/action threshold. The output is the construction impact memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
construction activity stage
  -> source power/vibration level
  -> receiver and distance map
  -> monitoring/action threshold
  -> construction impact memo
```

Task-card anchors:

- `distance-attenuation`
- `a-weighting`
- `vibration-transmissibility`
- `sediment-basin-sizing`
- `construction-tolerance`

Source pack:

- construction staging plan;
- equipment/source schedule;
- receiver map;
- monitoring criterion;
- complaint/action log.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change construction staging plan while keeping the downstream source power/vibration level fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make construction staging plan disagree with equipment/source schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in receiver map only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on construction activity stage. The response should show source power/vibration level and receiver and distance map, then record construction impact memo using the same source values throughout.

### SSC-12-LH-05: Rail Or Road Receiver Impact Package

This is a acoustic and vibration work package for rail or road receiver impact. It starts with the corridor plan/profile, traffic or train scenario, and receiver plan.

The engineer checks source level or vibration case, receiver geometry, and mitigation or operations branch. The output is the corridor impact memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
corridor alignment and speed/traffic case
  -> source level or vibration case
  -> receiver geometry
  -> mitigation or operations branch
  -> corridor impact memo
```

Task-card anchors:

- `davis-resistance`
- `distance-attenuation`
- `a-weighting`
- `vibration-transmissibility`
- `signal-sighting-distance`

Source pack:

- corridor plan/profile;
- traffic or train scenario;
- receiver plan;
- source spectrum;
- mitigation criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change corridor plan/profile while keeping the downstream source level or vibration case fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make corridor plan/profile disagree with traffic or train scenario about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in receiver plan only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on corridor alignment and speed/traffic case. The response should show source level or vibration case and receiver geometry, then record corridor impact memo using the same source values throughout.

### SSC-12-LH-06: Fire Alarm Audibility And Occupancy Package

This is a acoustic and vibration work package for fire alarm audibility and occupancy. It starts with the floor plan, NAC device schedule, and room finish schedule.

The engineer checks NAC or alarm source levels, room absorption/distance, and battery/load consequence. The output is the audibility memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
room/zone occupancy
  -> NAC or alarm source levels
  -> room absorption/distance
  -> battery/load consequence
  -> audibility memo
```

Task-card anchors:

- `nac-load-calculation`
- `sabine-rt60`
- `spl-log-sum`
- `battery-sizing`
- `occupant-load`

Source pack:

- floor plan;
- NAC device schedule;
- room finish schedule;
- fire alarm load table;
- life-safety criterion.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change floor plan while keeping the downstream NAC or alarm source levels fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make floor plan disagree with NAC device schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in room finish schedule only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on room/zone occupancy. The response should show NAC or alarm source levels and room absorption/distance, then record audibility memo using the same source values throughout.

### SSC-12-LH-07: Equipment Enclosure, Ventilation, And Noise Package

This is a acoustic and vibration work package for equipment enclosure, ventilation, and noise. It starts with the enclosure plan/section, ventilation schedule, and equipment spectrum.

The engineer checks ventilation/air change state, source spectrum and attenuation, and receiver check. The output is the enclosure design memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
equipment enclosure geometry
  -> ventilation/air change state
  -> source spectrum and attenuation
  -> receiver check
  -> enclosure design memo
```

Task-card anchors:

- `air-changes`
- `a-weighting`
- `distance-attenuation`
- `spl-log-sum`
- `pump-power-calculation`

Source pack:

- enclosure plan/section;
- ventilation schedule;
- equipment spectrum;
- receiver plan;
- attenuation treatment data.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change enclosure plan/section while keeping the downstream ventilation/air change state fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make enclosure plan/section disagree with ventilation schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in equipment spectrum only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on equipment enclosure geometry. The response should show ventilation/air change state and source spectrum and attenuation, then record enclosure design memo using the same source values throughout.

### SSC-12-LH-08: Acoustic Review Repair And Source-Policy Package

This is a acoustic and vibration work package for acoustic review repair and source-policy. It starts with the source index, octave spectra, and receiver plan.

The engineer checks review comment or changed operating mode, affected calculations, and repair ledger. The output is the response memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
source spectrum and receiver evidence
  -> review comment or changed operating mode
  -> affected calculations
  -> repair ledger
  -> response memo
```

Task-card anchors:

- `a-weighting`
- `spl-log-sum`
- `distance-attenuation`
- `sabine-rt60`
- `vibration-transmissibility`

Source pack:

- source index;
- octave spectra;
- receiver plan;
- comment register;
- criteria matrix.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change source index while keeping the downstream review comment or changed operating mode fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make source index disagree with octave spectra about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in receiver plan only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on source spectrum and receiver evidence. The response should show review comment or changed operating mode and affected calculations, then record response memo using the same source values throughout.

## How The Variants Come Together

All `SSC-12` variants should use the same acoustic receiver package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the acoustic receiver package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-12-LH-01` | Blower Or Pump Duty To Acoustic Impact Package | `source_register` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-12-LH-02` | Vibration Isolation And Support Package | `receiver_plan` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-12-LH-03` | Room Acoustic And HVAC Operations Package | `operating_scenario` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-12-LH-04` | Construction Noise And Vibration Monitoring Package | `spectral_basis` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-12-LH-05` | Rail Or Road Receiver Impact Package | `mitigation_state` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-12-LH-06` | Fire Alarm Audibility And Occupancy Package | `structural_path` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-12-LH-07` | Equipment Enclosure, Ventilation, And Noise Package | `criteria_targets` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-12-LH-08` | Acoustic Review Repair And Source-Policy Package | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The acoustic package should keep the same equipment noise, operating case, receiver location, spectra, attenuation path, room response, mitigation, and criteria across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

- **Real-world fit:** `SSC-12` is realistic when the task is treated as a source-path-receiver package: equipment duty and sound power spectrum, operating case, receiver location/category, shielding or enclosure mitigation, background level, vibration path, criteria, and final memo have to stay tied to the same source register. Useful source routes are FHWA [TNM and traffic-noise tools](https://www.fhwa.dot.gov/environment/noise/traffic_noise_model/), 23 CFR Part 772 [noise-abatement procedures](https://www.ecfr.gov/current/title-23/chapter-I/subchapter-H/part-772), FTA's [Transit Noise and Vibration Impact Assessment Manual](https://www.transit.dot.gov/sites/fta.dot.gov/files/docs/research-innovation/118131/transit-noise-and-vibration-impact-assessment-manual-fta-report-no-0123_0.pdf), [SoundPLANnoise](https://www.soundplan.eu/en/software/soundplannoise/), and DataKustik [CadnaA](https://www.datakustik.com/products/cadnaa/cadnaa).
- **Typical practitioner steps:** Register source IDs, operating scenario, octave-band or overall source data, receiver locations, distances, ground/shielding path, background or baseline measurements, criteria, and mitigation objects; compute or model receiver levels and vibration response; combine source and background exposure; compare against the governing criterion; then issue a memo that names the controlling source files, assumptions, margins, mitigation, and unresolved evidence gaps.
- **Software stack notes:** Practice commonly mixes spreadsheets and acoustic calculators for simple equipment checks, SoundPLAN or CadnaA for environmental noise maps and receiver tables, FHWA TNM for U.S. highway noise analysis, FTA methods for transit noise/vibration screening and detailed assessment, GIS/CAD receiver plans, measurement logs, vendor octave spectra, and mitigation sketches or model exports. The benchmark should treat these as source routes and workflow shapes, not hidden data.
- **Design implications:** A strong task should bind `source_register`, `operating_scenario`, `spectral_basis`, `receiver_plan`, `mitigation_state`, `background_condition`, `vibration_path`, and `criteria_targets` before calculations begin. Verifier checks should catch source/receiver drift, stale or unsupported criteria, octave-band handoff mutation, distance or shielding changes hidden in the memo, vibration isolation values copied without source support, and any claim that a synthetic package is accepted project evidence, full standards compliance, or benchmark-ready.

## Checks The Template Should Catch

These checks make `SSC-12` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `source_register` source object or evidence artifact. | `ssc_12_source_identity_mismatch` |
| Scenario drift | One stage uses a different `receiver_plan` case without a case-selection record. | `ssc_12_scenario_mismatch` |
| Geometry or topology drift | `operating_scenario` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_12_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_12_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_12_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_12_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_12_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_12_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_12_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_12_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-12-LH-01` Blower Or Pump Duty To Acoustic Impact Package: start here because it uses the main acoustic receiver package source files and produces a source-pack-sized memo.
2. `SSC-12-LH-02` Vibration Isolation And Support Package: add this after the first source pack has stable source files and control values.
3. `SSC-12-LH-03` Room Acoustic And HVAC Operations Package: add this after the first source pack has stable source files and control values.
4. `SSC-12-LH-04` Construction Noise And Vibration Monitoring Package: add this after the first source pack has stable source files and control values.

The next source-pack artifact should be a `acoustic_source_manifest.yaml` for one product. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-12 product into a source pack.

A first executable-quality source pack for `SSC-12` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `acoustic_source_manifest.yaml` | source fields such as `source_register`, `receiver_plan`, `operating_scenario`, `spectral_basis`, `mitigation_state` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `acoustic_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `acoustic_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as acoustic receiver package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
