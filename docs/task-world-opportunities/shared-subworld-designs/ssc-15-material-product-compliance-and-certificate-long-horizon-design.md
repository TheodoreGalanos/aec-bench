# SSC-15 Material/product compliance and certificate world Long-Horizon Design

This document treats product compliance as one source-controlled submittal package: certificates, datasheets, material properties, declared standards, installation limits, test evidence, and reviewer comments have to line up. A useful long-horizon task keeps that compliance basis consistent while moving between product selection, material checks, installation checks, certificates, review comments, and acceptance limits.

## Evidence Basis

| Field | Value |
| --- | --- |
| Compliance source state | mill/product certificate, material chemistry, mix design, product datasheet, code compliance note |
| Memberships | 14 task-card memberships |
| Primary cards | 6 |
| Disciplines | civil, electrical, mechanical, structural |
| Score | 24/30 |
| Candidate product | Product compliance package spanning steel, concrete, equipment, and electrical component data |
| Main risk | Often evidence assembly rather than long-horizon physical composition. |

The current card anchors cover material certificate, product datasheet, compliance, installation, material property, and review-packet checks:

| Card | Plain-language role |
| --- | --- |
| `driveway-gradient-check` | Driveway gradient calculation and compliance check per AS/NZS 2890.1:2004. |
| `pipe-velocity-check` | Pipe flow velocity compliance check against AS/NZS 3500.1 service-type limits. |
| `sewer-slope-check` | Gravity sewer slope adequacy check for self-cleansing velocity using Manning's equation. |
| `ac-resistance-temperature` | AC resistance of conductor at operating temperature including skin effect per IEC 60287. |
| `busbar-forces` | Busbar short-circuit electromagnetic force and stress calculation per IEEE 605 / IEC 60865-1. |
| `voltage-drop` | Cable voltage drop calculation per AS/NZS 3008.1.1. |
| `occupant-load` | Area-based occupant load calculation. |
| `por-aor-compliance` | Pump preferred and allowable operating range compliance. |
| `steel-critical-temp` | Critical steel temperature calculation from structural-fire load ratio. |
| `carbon-equivalent-calc` | IIW carbon equivalent calculation for structural steel weldability. |

## Product Compliance Data Model

Treat each task as a check against the same product compliance package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-15`, the product compliance package source state is:

```text
S_ssc_15 = {
  certificate_id,
  material_properties,
  product_selection,
  applicable_standard,
  use_case_boundary,
  calculation_dependency,
  substitution_state,
  authority_partition,
}
```

The product combinations below share the same product compliance package data. A change to certificate, datasheet, material property, declared standard, installation limit, test evidence, or reviewer comment must carry through each check.

```text
W_ssc15_lh_01 x_S W_ssc15_lh_02
W_ssc15_lh_02 x_S W_ssc15_lh_03
W_ssc15_lh_03 x_S W_ssc15_lh_04
W_ssc15_lh_04 x_S W_ssc15_lh_05
W_ssc15_lh_05 x_S W_ssc15_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_15` | The product compliance package source state that all combined checks must agree on. |
| `W_ssc15_lh_01` | The first SSC-15 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same product compliance package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Product Compliance Source Manifest

Any `SSC-15` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `certificate_id` | Mill certificate, product certificate, listing, datasheet, or compliance note identity. | certificate/datasheet |
| `material_properties` | Grade, chemistry, strength, temperature, corrosion, density, or electrical properties. | material table |
| `product_selection` | Selected product, variant, size, rating, listing, and manufacturer conditions. | submittal schedule |
| `applicable_standard` | Code, standard, listing, project criterion, and version. | standard/criteria |
| `use_case_boundary` | Where the material/product is used and what load/environment applies. | drawing/spec |
| `calculation_dependency` | Which formula/check consumes which certificate fields. | design memo |
| `substitution_state` | Approved, alternate, expired, region-specific, or rejected product state. | review response |
| `authority_partition` | Manufacturer, code, project spec, AHJ, and reviewer authority split. | submittal log |

## Candidate Long-Horizon Products

### SSC-15-LH-01: Steel Certificate To Structural/Fire/Carbon Package

This is a material and product compliance work package for steel certificate to structural/fire/carbon. It starts with the mill certificate, material schedule, and welding/fabrication criterion.

The engineer checks carbon equivalent or weldability check, structural/fire temperature consequence, and load/certificate alignment. The output is the material compliance memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
mill certificate and material grade
  -> carbon equivalent or weldability check
  -> structural/fire temperature consequence
  -> load/certificate alignment
  -> material compliance memo
```

Task-card anchors:

- `carbon-equivalent-calc`
- `steel-critical-temp`
- `load-combinations`
- `bracket-load-calc`
- `construction-tolerance`

Source pack:

- mill certificate;
- material schedule;
- welding/fabrication criterion;
- fire design note;
- structural calculation excerpt.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change mill certificate while keeping the downstream carbon equivalent or weldability check fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make mill certificate disagree with material schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in welding/fabrication criterion only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on mill certificate and material grade. The response should show carbon equivalent or weldability check and structural/fire temperature consequence, then record material compliance memo using the same source values throughout.

### SSC-15-LH-02: Cable/Component Datasheet To Ampacity And Voltage Package

This is a material and product compliance work package for cable/component datasheet to ampacity and voltage. It starts with the cable datasheet, cable schedule, and temperature/installation table.

The engineer checks cable/feed identity, ampacity and voltage-drop check, and temperature/derating branch. The output is the component compliance memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
product datasheet and rating table
  -> cable/feed identity
  -> ampacity and voltage-drop check
  -> temperature/derating branch
  -> component compliance memo
```

Task-card anchors:

- `cable-ampacity`
- `voltage-drop`
- `ac-resistance-temperature`
- `static-thermal-rating`
- `voltage-regulation`

Source pack:

- cable datasheet;
- cable schedule;
- temperature/installation table;
- SLD;
- manufacturer limits.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change cable datasheet while keeping the downstream cable/feed identity fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make cable datasheet disagree with cable schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in temperature/installation table only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on product datasheet and rating table. The response should show cable/feed identity and ampacity and voltage-drop check, then record component compliance memo using the same source values throughout.

### SSC-15-LH-03: Concrete Or Mix Compliance And Drainage/Retaining Use Package

This is a material and product compliance work package for concrete or mix compliance and drainage/retaining use. It starts with the mix design sheet, SCM/product data, and strength criterion.

The engineer checks target strength and SCM substitution, structural/foundation demand, and exposure or drainage context. The output is the mix compliance memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
mix design or certificate
  -> target strength and SCM substitution
  -> structural/foundation demand
  -> exposure or drainage context
  -> mix compliance memo
```

Task-card anchors:

- `target-strength-calc`
- `scm-substitution`
- `terzaghi-bearing-capacity`
- `retaining-wall-stability`
- `freeboard-calculation`

Source pack:

- mix design sheet;
- SCM/product data;
- strength criterion;
- foundation/retaining detail;
- exposure class note.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change mix design sheet while keeping the downstream target strength and SCM substitution fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make mix design sheet disagree with SCM/product data about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in strength criterion only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on mix design or certificate. The response should show target strength and SCM substitution and structural/foundation demand, then record mix compliance memo using the same source values throughout.

### SSC-15-LH-04: Product Submittal Review Packet Overlay

This is a material and product compliance work package for product submittal review packet overlay. It starts with the submittal register, datasheets, and certificates.

The engineer checks design calculation consumption, review comments, and substitution or rejection branch. The output is the submittal response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
datasheet/certificate source pack
  -> design calculation consumption
  -> review comments
  -> substitution or rejection branch
  -> submittal response
```

Task-card anchors:

- `por-aor-compliance`
- `carbon-equivalent-calc`
- `voltage-drop`
- `pipe-velocity-check`
- `occupant-load`

Source pack:

- submittal register;
- datasheets;
- certificates;
- calculation excerpts;
- review comments.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change submittal register while keeping the downstream design calculation consumption fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make submittal register disagree with datasheets about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in certificates only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on datasheet/certificate design files. The response should show design calculation consumption and review comments, then record submittal response using the same source values throughout.

### SSC-15-LH-05: Pipe Product Velocity, Slope, And Certificate Package

This is a material and product compliance work package for pipe product velocity, slope, and certificate. It starts with the pipe datasheet, pipe schedule, and long section.

The engineer checks slope/velocity check, certificate or lining limits, and hydraulic/design consequence. The output is the pipe product memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
pipe material/product identity
  -> slope/velocity check
  -> certificate or lining limits
  -> hydraulic/design consequence
  -> pipe product memo
```

Task-card anchors:

- `pipe-velocity-check`
- `sewer-slope-check`
- `sewer-pipe-sizing`
- `pressure-loss-calculation`
- `por-aor-compliance`

Source pack:

- pipe datasheet;
- pipe schedule;
- long section;
- velocity/slope criteria;
- certificate.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change pipe datasheet while keeping the downstream slope/velocity check fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make pipe datasheet disagree with pipe schedule about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in long section only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on pipe material/product identity. The response should show slope/velocity check and certificate or lining limits, then record pipe product memo using the same source values throughout.

### SSC-15-LH-06: Facade/Fixing Product Certificate And Capacity Package

This is a material and product compliance work package for facade/fixing product certificate and capacity. It starts with the product certificate, capacity table, and facade elevation.

The engineer checks certificate/resistance table, wind/bracket demand, and material/weldability check. The output is the submittal memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
facade/fixing product identity
  -> certificate/resistance table
  -> wind/bracket demand
  -> material/weldability check
  -> submittal memo
```

Task-card anchors:

- `bracket-load-calc`
- `carbon-equivalent-calc`
- `design-wind-pressure`
- `load-combinations`
- `construction-tolerance`

Source pack:

- product certificate;
- capacity table;
- facade elevation;
- wind/bracket calculation;
- material schedule.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change product certificate while keeping the downstream certificate/resistance table fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make product certificate disagree with capacity table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in facade elevation only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on facade/fixing product identity. The response should show certificate/resistance table and wind/bracket demand, then record submittal memo using the same source values throughout.

### SSC-15-LH-07: Code Compliance Note For Occupancy/Fire/Product Class

This is a material and product compliance work package for code compliance note for occupancy/fire/product class. It starts with the occupancy schedule, product datasheet, and fire/hazard class note.

The engineer checks product/material class, authority criterion, and affected calculations. The output is the compliance response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
occupancy or hazard context
  -> product/material class
  -> authority criterion
  -> affected calculations
  -> compliance response
```

Task-card anchors:

- `occupant-load`
- `steel-critical-temp`
- `nac-load-calculation`
- `visibility-criterion`
- `air-changes`

Source pack:

- occupancy schedule;
- product datasheet;
- fire/hazard class note;
- standard/authority reference;
- calculation appendix.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change occupancy schedule while keeping the downstream product/material class fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make occupancy schedule disagree with product datasheet about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in fire/hazard class note only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on occupancy or hazard context. The response should show product/material class and authority criterion, then record compliance response using the same source values throughout.

### SSC-15-LH-08: Certificate Conflict And Repair Portfolio

This is a material and product compliance work package for certificate conflict and repair portfolio. It starts with the two product datasheets, certificate record, and source index.

The engineer checks source authority selection, affected stage calculations, and replacement/substitution case. The output is the repair memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
conflicting certificates or datasheets
  -> source authority selection
  -> affected stage calculations
  -> replacement/substitution case
  -> repair memo
```

Task-card anchors:

- `carbon-equivalent-calc`
- `voltage-drop`
- `cable-ampacity`
- `target-strength-calc`
- `pipe-velocity-check`

Source pack:

- two product datasheets;
- certificate record;
- source index;
- calculation trace;
- review response.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change two product datasheets while keeping the downstream source authority selection fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make two product datasheets disagree with certificate record about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in source index only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on conflicting certificates or datasheets. The response should show source authority selection and affected stage calculations, then record repair memo using the same source values throughout.

## How The Variants Come Together

All `SSC-15` variants should use the same product compliance package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the product compliance package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-15-LH-01` | Steel Certificate To Structural/Fire/Carbon Package | `certificate_id` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-15-LH-02` | Cable/Component Datasheet To Ampacity And Voltage Package | `material_properties` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-15-LH-03` | Concrete Or Mix Compliance And Drainage/Retaining Use Package | `product_selection` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-15-LH-04` | Product Submittal Review Packet Overlay | `applicable_standard` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-15-LH-05` | Pipe Product Velocity, Slope, And Certificate Package | `use_case_boundary` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-15-LH-06` | Facade/Fixing Product Certificate And Capacity Package | `calculation_dependency` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-15-LH-07` | Code Compliance Note For Occupancy/Fire/Product Class | `substitution_state` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-15-LH-08` | Certificate Conflict And Repair Portfolio | `authority_partition` | Keeps this control point consistent across the source pack, calculations, and memo. |

The compliance package should keep the same certificates, datasheets, material properties, declared standards, installation limits, test evidence, and reviewer comments across the calculations, handoffs, criteria checks, and design memo.

## Domain Practice Notes

Real-world fit:

- This is realistic when the package is treated as a submittal and evidence-control workflow, not as a material lookup. Real projects reconcile mill certificates, product datasheets, evaluation reports, approvals, test standards, installation limits, substitutions, reviewer comments, and downstream calculations that rely on declared properties.
- The useful long-horizon behaviour appears when one product certificate has consequences in another discipline: steel properties drive structural/fire/carbon checks, cable datasheets drive ampacity/voltage checks, facade certificates drive fixing capacity, and product substitutions reopen authority or reviewer decisions.
- The package should preserve source status. A current certificate, expired report, manufacturer datasheet, third-party listing, and reviewer comment are not interchangeable evidence even when they name the same product family.

Typical practitioner steps:

1. Register certificate IDs, report dates, product codes, declared standards, material properties, installation limits, test evidence, expiry or accreditation status, and reviewer comments.
2. Map each property or limit to the calculation, drawing, specification, compliance matrix, or submittal response that consumes it.
3. Check substitutions, conflicting certificates, missing test routes, regional approval differences, and calculation dependencies before accepting the product.
4. Issue a compliance memo that names source status, applicable standard, use-case boundary, accepted properties, rejected assumptions, and unresolved evidence gaps.

Software stack notes:

- [ICC-ES evaluation reports](https://www.icc-es.org/evaluation-report-program/reports-directory/) are a realistic North American report route for products needing code-evaluation evidence rather than only manufacturer datasheets.
- [UL Product iQ](https://productiq.ulprospector.com/) is a realistic listing-directory route for electrical, fire, and product-safety evidence; source packs should preserve listing category, product identity, and edition/status boundaries.
- [FM Approvals](https://www.fmapprovals.com/) and [RoofNav](https://www.fmapprovals.com/products-we-certify/roofnav) are realistic approval routes for property-risk, fire, roof, and industrial product evidence.
- [BBA certificates](https://www.bbacerts.co.uk/) are realistic UK construction-product certificate routes, but current accreditation/status notes are time-sensitive and must be captured explicitly if a source pack treats BBA as an active certification authority.

Design implications:

- Add `certificate_register`, `product_selection_register`, `applicable_standard_matrix`, `source_status_ledger`, `calculation_dependency_map`, and `review_comment_log` fields before hardening `SSC-15-LH-04`.
- Require certificate/report IDs, product codes, property names, limits, dates, source status, and consuming calculation IDs to survive through the compliance memo.
- Negative cases should include an expired or wrong-region certificate accepted as current, a product substitution that leaves the old capacity in a calculation, and a reviewer comment closed without source evidence.

## Checks The Template Should Catch

These checks make `SSC-15` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `certificate_id` source object or evidence artifact. | `ssc_15_source_identity_mismatch` |
| Scenario drift | One stage uses a different `material_properties` case without a case-selection record. | `ssc_15_scenario_mismatch` |
| Geometry or topology drift | `product_selection` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_15_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `authority_partition` are treated as interchangeable. | `ssc_15_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_15_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_15_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_15_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_15_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_15_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_15_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-15-LH-01` Steel Certificate To Structural/Fire/Carbon Package: start here because it uses the main product compliance package source files and produces a source-pack-sized memo.
2. `SSC-15-LH-02` Cable/Component Datasheet To Ampacity And Voltage Package: add this after the first source pack has stable source files and control values.
3. `SSC-15-LH-03` Concrete Or Mix Compliance And Drainage/Retaining Use Package: add this after the first source pack has stable source files and control values.
4. `SSC-15-LH-04` Product Submittal Review Packet Overlay: add this after the first source pack has stable source files and control values.

The next artifact should be a `compliance_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-15 product into a source pack.

A first executable-quality source pack for `SSC-15` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `compliance_source_manifest.yaml` | source fields such as `certificate_id`, `material_properties`, `product_selection`, `applicable_standard`, `use_case_boundary` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `compliance_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `compliance_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as product compliance package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
