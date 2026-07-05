# SSC-20 Regional standards, authority, and review packet overlay Long-Horizon Design

This document treats regional standards and review comments as one source-controlled authority package: jurisdiction, standard version, applicability rule, submission contents, review state, conflicts, and source policy have to line up. A useful long-horizon task keeps that authority basis consistent while moving between criteria selection, permit forms, calculation attachments, review comments, exceptions, and response memos.

## Evidence Basis

| Field | Value |
| --- | --- |
| Authority source state | standard/owner/AHJ criteria, permits, forms, design report package, source authority gates |
| Memberships | 0 task-card memberships |
| Primary cards | 0 |
| Disciplines | authority overlay |
| Score | 0/30 |
| Candidate product | Authority overlay for any design package |
| Main risk | Overlay only; not ranked as a physical product cluster. |

The current card anchors cover authority, owner, permit, standards, submission, checklist, comment, and response checks:

| Card | Plain-language role |
| --- | --- |
| `authority overlay across all product clusters` | Applies owner, regulator, utility, insurer, or reviewer requirements to a design package. |

## Authority Review Data Model

Treat each task as a check against the same authority review package source pack: drawings, schedules, calculations, design response, and audit trail.

```text
W = {source files, extracted source data, calculations, design response, audit trail}
```

For `SSC-20`, the authority review package source state is:

```text
S_ssc_20 = {
  authority_id,
  jurisdiction_region,
  standard_version,
  applicability_rule,
  submission_packet,
  review_state,
  conflict_ledger,
  source_policy,
}
```

The product combinations below share the same authority review package data. A change to authority, jurisdiction, standard version, applicability rule, submission packet, review state, conflict, or source policy must carry through each check.

```text
W_ssc20_lh_01 x_S W_ssc20_lh_02
W_ssc20_lh_02 x_S W_ssc20_lh_03
W_ssc20_lh_03 x_S W_ssc20_lh_04
W_ssc20_lh_04 x_S W_ssc20_lh_05
W_ssc20_lh_05 x_S W_ssc20_lh_06
```

Notation for this block:

| Symbol | Meaning in this document |
| --- | --- |
| `W` | One task check: its source files, extracted source data, calculations, final response, and audit trail. |
| `S_ssc_20` | The authority review package source state that all combined checks must agree on. |
| `W_ssc20_lh_01` | The first SSC-20 long-horizon product below. |
| `x_S` | Combine two checks while forcing them to use the same authority review package source state. |

For example, the first two products must use the same source files, design case, physical layout, controlling criteria, and handoff values. If one product changes a key source value, the other product must either inherit that change or flag a source conflict.

The check is whether the same source file, design case, physical layout, controlling criteria, and handoff values survive as the work moves between disciplines.

## Authority Review Source Manifest

Any `SSC-20` source file set should make these fields explicit.

| Manifest Field | Meaning | Typical Source |
| --- | --- | --- |
| `authority_id` | AHJ, owner, utility, rail operator, insurer, municipality, or reviewer identity. | criteria matrix |
| `jurisdiction_region` | Country, state, local council, DNSP, operator, project region, or client overlay. | regional map |
| `standard_version` | Named standard, version, amendment, date, and access state. | standard metadata |
| `applicability_rule` | What triggers the rule and what it excludes. | scope clause/criteria note |
| `submission_packet` | Drawings, forms, calculations, datasheets, reports, and checklists required. | review checklist |
| `review_state` | Draft, submitted, commented, approved, rejected, superseded, or deferred. | review log |
| `conflict_ledger` | Conflicts between owner, code, utility, insurer, product, and project criteria. | decision log |
| `source_policy` | Open/gated/licensed/redrawn/task-owned source status and citation boundary. | source register |

## Candidate Long-Horizon Products

### SSC-20-LH-01: Regional Standards Overlay For Any Design Package

This is a regional standards and authority review work package for regional standards overlay for any design. It starts with the design files from a physical discipline package, standards matrix, and owner/AHJ criteria.

The engineer checks regional/owner standard selection, criteria mapping, and affected design decisions. The output is the standards overlay memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
physical discipline design files
  -> regional/owner standard selection
  -> criteria mapping
  -> affected design decisions
  -> standards overlay memo
```

Task-card anchors:

- `load-combinations`
- `hgl-check`
- `battery-sizing`
- `incident-energy`
- `occupant-load`

Source pack:

- design files from a physical discipline package;
- standards matrix;
- owner/AHJ criteria;
- decision ledger;
- review response template.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change design files from a physical discipline package while keeping the downstream regional/owner standard selection fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make design files from a physical discipline package disagree with standards matrix about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in owner/AHJ criteria only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on physical discipline design files. The response should show regional/owner standard selection and criteria mapping, then record standards overlay memo using the same source values throughout.

### SSC-20-LH-02: Permit And Submission Completeness Package

This is a regional standards and authority review work package for permit and submission completeness. It starts with the submission checklist, permit form, and drawing/calculation index.

The engineer checks required permit forms, calculation and drawing attachments, and missing-evidence check. The output is the submission memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
design package manifest
  -> required permit forms
  -> calculation and drawing attachments
  -> missing-evidence check
  -> submission memo
```

Task-card anchors:

- `por-aor-compliance`
- `freeboard-calculation`
- `retaining-wall-stability`
- `sprinkler-discharge`
- `voltage-drop`

Source pack:

- submission checklist;
- permit form;
- drawing/calculation index;
- source-policy table;
- comment register.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change submission checklist while keeping the downstream required permit forms fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make submission checklist disagree with permit form about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in drawing/calculation index only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on design package manifest. The response should show required permit forms and calculation and drawing attachments, then record submission memo using the same source values throughout.

### SSC-20-LH-03: Authority Conflict And Repair Package

This is a regional standards and authority review work package for authority conflict and repair. It starts with the two standards/owner criteria excerpts, design files manifest, and branch ledger.

The engineer checks physical design state, affected design decision, and repair or exception path. The output is the authority response. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
two conflicting criteria sources
  -> physical design state
  -> affected design decision
  -> repair or exception path
  -> authority response
```

Task-card anchors:

- `design-wind-speed`
- `incident-energy`
- `retaining-wall-stability`
- `hgl-check`
- `occupant-load`

Source pack:

- two standards/owner criteria excerpts;
- source pack manifest;
- branch ledger;
- calculation excerpts;
- exception/comment register.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change two standards/owner criteria excerpts while keeping the downstream physical design state fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make two standards/owner criteria excerpts disagree with source pack manifest about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in branch ledger only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on two conflicting criteria sources. The response should show physical design state and affected design decision, then record authority response using the same source values throughout.

### SSC-20-LH-04: Source-Policy And Redrawn-Fixture Boundary Package

This is a regional standards and authority review work package for source-policy and redrawn-fixture boundary. It starts with the source index, redrawn drawing/table, and license/redistribution note.

The engineer checks redrawn fixture boundary, derived value policy, and response-language constraints. The output is the source-policy memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
public/private/task-owned source inventory
  -> redrawn fixture boundary
  -> derived value policy
  -> response-language constraints
  -> source-policy memo
```

Task-card anchors:

- `bracket-load-calc`
- `detention-volume-preliminary`
- `water-supply-curve`
- `grid-resistance`
- `signal-sighting-distance`

Source pack:

- source index;
- redrawn drawing/table;
- license/redistribution note;
- derived-data ledger;
- expected output boundary.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change source index while keeping the downstream redrawn fixture boundary fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make source index disagree with redrawn drawing/table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in license/redistribution note only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on public/private/task-owned source inventory. The response should show redrawn fixture boundary and derived value policy, then record source-policy memo using the same source values throughout.

### SSC-20-LH-05: Regional Variant Matrix For A Physical Product

This is a regional standards and authority review work package for regional variant matrix for a physical design. It starts with the physical discipline design files, regional criteria table, and variant matrix.

The engineer checks regional rule variants, changed design outcomes, and unchanged physical invariants. The output is the variant comparison memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
baseline physical design
  -> regional rule variants
  -> changed design outcomes
  -> unchanged physical invariants
  -> variant comparison memo
```

Task-card anchors:

- `load-combinations`
- `voltage-drop`
- `freeboard-calculation`
- `egress-width`
- `sprinkler-discharge`

Source pack:

- physical discipline design files;
- regional criteria table;
- variant matrix;
- expected-output table;
- diagnostic map.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change physical discipline design files while keeping the downstream regional rule variants fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make physical discipline design files disagree with regional criteria table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in variant matrix only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on baseline physical design. The response should show regional rule variants and changed design outcomes, then record variant comparison memo using the same source values throughout.

### SSC-20-LH-06: Review Comment Ledger And Design Response Package

This is a regional standards and authority review work package for review comment ledger and design response. It starts with the comment register, source index, and handoff ledger.

The engineer checks source-handoff mapping, changed calculations, and accepted/rejected responses. The output is the design response memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
review comments
  -> source-handoff mapping
  -> changed calculations
  -> accepted/rejected responses
  -> design response memo
```

Task-card anchors:

- `hgl-check`
- `bracket-load-calc`
- `battery-sizing`
- `retaining-wall-stability`
- `signal-sighting-distance`

Source pack:

- comment register;
- source index;
- handoff ledger;
- calculation excerpts;
- response matrix.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change comment register while keeping the downstream source-handoff mapping fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make comment register disagree with source index about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in handoff ledger only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on review comments. The response should show source-handoff mapping and changed calculations, then record design response memo using the same source values throughout.

### SSC-20-LH-07: Standards Edition Drift And Regression Package

This is a regional standards and authority review work package for standards edition drift and regression. It starts with the standards matrix, edition comparison table, and calculation design files.

The engineer checks updated edition or owner supplement, affected thresholds, and regression comparison. The output is the edition-drift memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
baseline standard edition
  -> updated edition or owner supplement
  -> affected thresholds
  -> regression comparison
  -> edition-drift memo
```

Task-card anchors:

- `design-wind-speed`
- `incident-energy`
- `cable-ampacity`
- `freeboard-calculation`
- `occupant-load`

Source pack:

- standards matrix;
- edition comparison table;
- calculation source pack;
- expected changed gates;
- non-claim boundary.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change standards matrix while keeping the downstream updated edition or owner supplement fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make standards matrix disagree with edition comparison table about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in calculation source pack only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on baseline standard edition. The response should show updated edition or owner supplement and affected thresholds, then record edition-drift memo using the same source values throughout.

### SSC-20-LH-08: Acceptance Evidence And Non-Claim Boundary Package

This is a regional standards and authority review work package for acceptance evidence and non-claim boundary. It starts with the source index, expected output, and accepted/project evidence if available.

The engineer checks acceptance artifacts present or absent, language gate for certification claims, and gap register. The output is the final evidence memo. The design response should name the controlling input values and show where the result is recorded.

Composition:

```text
design output and evidence pack
  -> acceptance artifacts present or absent
  -> language gate for certification claims
  -> gap register
  -> final evidence memo
```

Task-card anchors:

- `por-aor-compliance`
- `available-flow-calculation`
- `bracket-load-calc`
- `detention-volume-preliminary`
- `grid-resistance`

Source pack:

- source index;
- expected output;
- accepted/project evidence if available;
- gap register;
- language-policy checklist.

Variants:

| Variant | What Changes | What The Check Should Catch |
| --- | --- | --- |
| Governing case swap | Change source index while keeping the downstream acceptance artifacts present or absent fixed. | Confirms the selected design case is recorded before the result changes. |
| Source conflict | Make source index disagree with expected output about the controlling value or object. | Confirms which drawing, schedule, report, or model controls the value. |
| Object relocation | Move the controlling asset, receiver, support, or boundary in accepted/project evidence if available only. | Confirms the asset, receiver, connection, support, or model object stays consistent. |
| Authority override | Apply a reviewer, owner, manufacturer, or regional criterion that changes the governing case. | Confirms the design response names the owner, code, manufacturer, discipline, or authority criterion that controls the decision. |
| Unsupported downstream repair | Let the final memo alter downstream values without resolving the source or decision conflict. | Confirms the memo does not change downstream values without resolving the source conflict. |

Best use:

Use this when the decision depends on design output and evidence pack. The response should show acceptance artifacts present or absent and language gate for certification claims, then record final evidence memo using the same source values throughout.

## How The Variants Come Together

All `SSC-20` variants should use the same authority review package workflow:

```text
source file register
  -> source data table
  -> criteria and design-case selection
  -> discipline calculations and handoff values
  -> result table and design memo
  -> checks for source, case, handoff, and memo errors
```

Each product starts from a different control point in the authority review package package.

| Product | Product Family | Main Control Point | Why It Matters |
| --- | --- | --- | --- |
| `SSC-20-LH-01` | Regional Standards Overlay For Any Design Package | `authority_id` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-20-LH-02` | Permit And Submission Completeness Package | `jurisdiction_region` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-20-LH-03` | Authority Conflict And Repair Package | `standard_version` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-20-LH-04` | Source-Policy And Redrawn-Fixture Boundary Package | `applicability_rule` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-20-LH-05` | Regional Variant Matrix For A Physical Product | `submission_packet` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-20-LH-06` | Review Comment Ledger And Design Response Package | `review_state` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-20-LH-07` | Standards Edition Drift And Regression Package | `conflict_ledger` | Keeps this control point consistent across the source pack, calculations, and memo. |
| `SSC-20-LH-08` | Acceptance Evidence And Non-Claim Boundary Package | `source_policy` | Keeps this control point consistent across the source pack, calculations, and memo. |

The authority review package should keep the same jurisdiction, standard version, applicability rule, submission contents, review state, conflicts, and source policy across the calculations, handoffs, criteria checks, and design memo.

## Power Playground Skill-Derived Task Candidates

These candidates translate the local `Power-Playground-main` SME review skills into this SSC. They are design-note candidates only; they do not add runnable templates, accepted evidence, or source-pack hardening.

| Candidate Task | Source Skill | Source Pack Shape | What The Check Should Catch |
| --- | --- | --- | --- |
| Can a review checklist become an auditable action register? | `templates/review-skill` | Primary deliverable, checklist items, evidence citations, `[P]`/`[F]`/`[N/A]`/`[ID]` statuses, findings, and action list. | Checklist items are skipped, failures lack actions, insufficient-data items do not name the missing data, or action priorities do not match the risk basis. |
| Which authority or standard basis controls this electrical review? | `hv-power-system-review`, `earthing-study-review`, and `protection-study-review` | Standards register, project criteria, utility/client requirements, review scope, source index, and discipline review checklist. | Owner, utility, Australian standard, international standard, reviewer, and discipline criteria are collapsed into one generic approval basis. |
| What evidence is enough to say pass, fail, not applicable, or insufficient data? | All Power Playground review skills | Source file inventory, citation map, checklist status table, missing-data list, and verification pass. | The response treats absence of evidence as a pass, marks items not applicable without scope rationale, or invents values to avoid `[ID]`. |
| Does the review avoid certification and benchmark-readiness overclaim? | `substation-safe-design-assessment` and `templates/review-skill` | Review disclaimer, evidence boundary, action list, verification log, and non-claim policy. | A GA screening or checklist review is described as formal compliance certification, accepted project evidence, executable verifier readiness, or benchmark-ready evidence. |

## Checks The Template Should Catch

These checks make `SSC-20` more than a stack of separate calculations.

| Event | Broken Assumption | Failure Code |
| --- | --- | --- |
| Source identity drift | The response changes the controlling `authority_id` source object or evidence artifact. | `ssc_20_source_identity_mismatch` |
| Scenario drift | One stage uses a different `jurisdiction_region` case without a case-selection record. | `ssc_20_scenario_mismatch` |
| Geometry or topology drift | `standard_version` is interpreted with the wrong asset, station, zone, node, receiver, or support. | `ssc_20_object_identity_drift` |
| Authority collapse | Owner, regulator, manufacturer, and discipline criteria under `source_policy` are treated as interchangeable. | `ssc_20_authority_partition_mismatch` |
| Handoff mutation | A downstream stage consumes a renamed, unit-changed, or silently adjusted intermediate value. | `ssc_20_handoff_mutation` |
| Missing result ledger | The final response gives plausible numbers without enough intermediate values to audit the chain. | `ssc_20_result_ledger_gap` |
| Unsupported source value | The response invents a value absent from the declared source pack or derived tables. | `ssc_20_source_policy_violation` |
| Branch explanation missing | The governing product, standard, regime, material, or operating mode is chosen only in prose. | `ssc_20_branch_trace_missing` |
| Negative case swallowed | A deliberate bad variant is absorbed as a normal design choice. | `ssc_20_negative_case_swallowed` |
| Readiness overclaim | A design note or fixture seed is described as an accepted project, executable verifier, or benchmark-ready task. | `ssc_20_readiness_overclaim` |

## Recommended Hardening Order

1. `SSC-20-LH-01` Regional Standards Overlay For Any Design Package: start here because it uses the main authority review package source files and produces a source-pack-sized memo.
2. `SSC-20-LH-02` Permit And Submission Completeness Package: add this after the first source pack has stable source files and control values.
3. `SSC-20-LH-03` Authority Conflict And Repair Package: add this after the first source pack has stable source files and control values.
4. `SSC-20-LH-04` Source-Policy And Redrawn-Fixture Boundary Package: add this after the first source pack has stable source files and control values.

The next artifact should be a `authority_review_source_manifest.yaml` for one product, not runtime code. That manifest should define source files, source keys, design-case choices, controlling criteria, handoff values, expected outputs, and failure cases.

## Source-Pack Build Notes

These notes define the first file set needed to turn one SSC-20 product into a source pack.

A first executable-quality source pack for `SSC-20` should include:

| File | Required Content | Why It Exists |
| --- | --- | --- |
| `project.yaml` | cluster ID, product ID, source policy, region/owner context, and fixture status | Prevents design research from being mistaken for accepted project evidence. |
| `source-index.md` | every source artifact, source type, authority role, redistribution status, and derived table | Makes source authority explicit before values are calculated. |
| `authority_review_source_manifest.yaml` | source fields such as `authority_id`, `jurisdiction_region`, `standard_version`, `applicability_rule`, `submission_packet` | Defines the source data that every check must reuse. |
| `stage-graph.yaml` | ordered checks, consumed sources, produced handoffs, and active built-in template anchors | Makes the design sequence inspectable. |
| `case-ledger.yaml` | governing cases, standards choices, product classes, scenario decisions, and source references | Records the design cases and criteria selected from the source pack. |
| `handoff-ledger.yaml` | named intermediate values with units, source stage, downstream consumers, tolerances, and basis | Records values passed from one calculation to the next. |
| `verification-rules.yaml` | source-file checks, case-selection checks, handoff checks, calculation checks, and response checks | Defines the checks before implementation. |
| `verification-cases.yaml` | baseline pass plus localized negative cases for source, branch, handoff, and response failures | Prevents only happy-path evaluation. |
| `expected-output.md` | structured response fields, accepted evidence language, unresolved-gap language, and non-claims | Gives agents a concrete deliverable target. |

A valid response should include source references, a populated `authority_review_source_manifest.yaml`, design-case choices, handoff values, a result table, and explicit limits. It should not claim accepted design status, full standards compliance, source-pack hardening, executable verifier readiness, or benchmark readiness until those artifacts exist.

## Boundary And Non-Claims

These documents are intentionally detailed design artifacts, not runnable benchmark implementations.

- They do not claim accepted project status, code certification, or authority approval.
- They do not claim that source artifacts have already been licensed, packaged, parsed, or redistributed.
- They do not claim executable verifier implementation or generated benchmark instances.
- They are meant to make the next artifact concrete: a `authority_review_source_manifest.yaml` for one selected product, followed by source files, case ledgers, handoff ledgers, verification cases, and response contracts.
- They should be used as authority review package product notes, while the source-pack build notes should be used only to guide later fixture packaging.
