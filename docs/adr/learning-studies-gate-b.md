# Learning Studies Gate B

| Field | Value |
| --- | --- |
| Class | Decision |
| Status | Current |
| Date | 2026-08-23 |
| Scope | Lifecycle-derived Learning Studies substrate; authorises Stage C (bounded worlds) integration |

## Decision

Gate B passes with **zero common substrate changes**. Every LS-08 question
resolves to "keep it where it already lives." No field is added to, removed
from, or moved between `src/aec_bench/contracts/learning_study.py`,
`learning_study_evidence.py`, `learning_study_assessment.py`, or
`learning_family.py`, and none of `planning.py`, `runtime.py`, `assessment.py`,
`recording.py`, `resume.py`, or `protocol_collection.py` under
`src/aec_bench/experimentation/learning_studies/` changes. This mirrors Gate A:
the common layer stays an optional composition over `PlannedTrial` and
`TrialRecord`, and Stage B (lifecycles) demonstrated the same substrate serves
a second, structurally distinct environment family without modification.

This decision authorises **Stage C — bounded worlds** (PRD LS-09, the dam-
seepage world) to begin integration against the substrate as documented in
`docs/adr/learning-studies-gate-a.md` and this record, unchanged.

## Evidence used

- `docs/adr/learning-studies-lifecycle-l01-review.md` (L01 architecture
  review): field-by-field decision table (§4), common-substrate decision of
  zero changes (§5), adapter/harness ownership split (§6), the finding that
  LS-07B (new lifecycle evidence design) was not triggered (§11), and the L02
  input requirements (§9).
- `docs/research/learning-studies/l01-deterministic-evidence.md`: the fixed
  three-arm protocol, feedback-boundary field list, outcome-projection
  callback table, and deterministic isolation results.
- `docs/research/learning-studies/l01-relation-domain-review.md`: independent
  domain review of the `l01-lifecycle-staged-evidence-transfer` relation
  (purpose `transfer`).
- `src/aec_bench/contracts/learning_study.py`,
  `learning_study_evidence.py`, `learning_study_assessment.py`: read directly
  to confirm the authored contract shape is unchanged since Gate A.
- `src/aec_bench/experimentation/learning_studies/lifecycles.py`,
  `lifecycle_learning_state.py`, `l01_drainage.py`: read directly to confirm
  adapter ownership claims below against the actual implementation.

## Questions resolved (PRD LS-08)

### 1. Hierarchical evidence

**No common `LearningUnitRef` envelope is added.**

The promotion rule (LS-08) requires either (a) at least one artifact study and
one lifecycle study using the concept, or (b) a demonstrated requirement from
upcoming world evidence. Neither is met:

- L01 used complete-trial outcomes exclusively. Its five measured pairs are
  all lifecycle-vs-lifecycle probe comparisons (L01 review §3); no phase,
  checkpoint, or sub-trial unit was referenced by any measurement, relation,
  or assessment fact.
- Phase and checkpoint concepts stayed lifecycle-owned throughout: the L01
  review's field-by-field table (§4) keeps lifecycle target resolution,
  execution-condition fixing, and treatment semantics entirely
  `KEEP ADAPTER-LOCAL`; the common-substrate decision (§5) is zero changes.
  PRD LS-07 (deferred, not yet built) proposes `LifecycleLearningEvidence` as
  an optional *lifecycle-owned typed extension artefact*, explicitly stating
  "the common study layer references phase IDs without interpreting them" —
  i.e. even the planned future design does not ask for a common envelope.
- The planned bounded dam-world studies (PRD LS-09) intend to use
  complete-trial outcomes plus task-owned action evidence (`actor action`,
  `pre-/post-action evidence state`, `accepted or rejected`, `information
  released`, `decision relevance`, `terminal consequence` —
  `programme.md` "Task-owned action evidence"). The dam-world owner can emit
  this evidence as its own typed artefact, the same pattern L01's drainage
  gates already use, without a common hierarchical reference.

### 2. Feedback schedule

**Keep the single explicit terminal `ReleaseFeedbackStep` unchanged.**

L01 used exactly one explicit feedback-release step per exposed arm, after
acquisition and before the probe (`l01-deterministic-evidence.md`, "Fixed
protocol" and "Feedback boundary"). The deterministic proof directly exercises
what this explicitness buys: flipping `probe_state_discarded` or
`hidden_evaluation_leaked` in a test degrades every affected measurement to
`INVALID` (L01 review §3), and a dedicated test now proves cross-arm feedback
restore is rejected (L01 review §10). The step-level explicitness — a named,
separately timed, separately recorded operation — is what makes
"probe feedback was not released" a provable fact rather than an assumption.
Simplifying it away would remove the exact mechanism the isolation proof
depends on. PRD LS-07's proposed feedback-schedule variants (no feedback,
immediate, delayed, summary-after-phase) are lifecycle-owned scheduling
choices layered on top of the same step primitive, not a reason to change it.

### 3. Learner continuity

**No lifecycle continuity requirement leaves the adapter.**

The L01 review's common-substrate decision (§5) states plainly: no common
Learning Studies contract, enum, channel, registry, phase, or provider field
was added or changed, and `git status` against the merge base showed zero
modifications under the common contracts and runtime modules. Concretely
(§4, §6):

- the `memory/` + `feedback/` learner-state tree, its size/type/symlink/
  case-collision validation, and copy-on-write transitions are owned by
  `lifecycle_learning_state.py` and `lifecycles.py`, not the common layer;
- the read-only context projection (`learner_context/`) is built and
  byte-compared by the adapter and exposed through one generic,
  Learning-Studies-neutral harness parameter
  (`read_only_context_root`) that carries no arm/state/treatment/probe
  identifiers (§6, confirmed by
  `test_workspace_policy_labels_context_as_non_authoritative`);
- `reset` and `structured-memory` treatment semantics, the adapter-ID
  convention (`lifecycle-local:<mode>:<visibility>`), and execution-condition
  fixing are all `KEEP ADAPTER-LOCAL` in the field-by-field table.

This is the same shape Gate A found for the artifact adapter (Gate A,
"Adapter-owned concepts"): the common layer sees opaque state, explicit
feedback identity, normal trials, and task-owned projection values only. A
second, structurally different adapter reusing exactly this boundary is
positive evidence the boundary is already correctly drawn, not evidence that
something should move.

### 4. Outcome projections

**Keep named outcome projections as function callbacks.**

`OutcomeProjection = Callable[[TrialRecord], ProjectionResult]`
(`experimentation/learning_studies/assessment.py`) is unchanged since Gate A
and has now been proven sufficient across two independent projection sources:
the artifact task-owned projections exercised in Release A, and L01's five
lifecycle projections — `lifecycle.canonical-reward` and the four
`drainage.*` gate projections (`l01-deterministic-evidence.md`, "Outcome
projections"), all supplied directly by `drainage_learning.py` with no
Learning Studies imports (L01 review, implementation summary). A persisted
registry would add identity, versioning, and lookup machinery that no study
to date has needed; it remains speculative per the same reasoning Gate A used
to reject a callback registry (Gate A, "Consequences and open questions").

### 5. Study relations

**No relation purpose beyond `transfer` / `boundary` / `composition` is
needed.**

L01 is registered and reviewed as a `transfer` relation
(`l01-lifecycle-staged-evidence-transfer`; independently reviewed in
`l01-relation-domain-review.md`). The next lifecycle study explicitly planned
in the programme — "an applicability or review-boundary case"
(`programme.md`, PRD LS-06 "Initial studies") — is scoped to use `boundary`,
already an existing `ExperienceRelationPurpose` value from Gate A. No lifecycle
evidence produced or planned so far exercises a comparison shape the three
existing purposes cannot express; `retention` and `interference` remain
correctly absent as separate relation purposes, per Gate A's original finding
that sequence roles and named measurements already own those questions.

## Evidence limitations

Gate B is closed on one lifecycle family (drainage staged-evidence transfer,
deterministic only) — LS-07 phase-evidence studies have not run, and the
planned L02 boundary campaign has not executed. This is acceptable here
specifically because **every answer above is a non-promotion**: the gate's
purpose is to guard against prematurely universalising a lifecycle-specific
concept into the common substrate, and declining to universalise anything
carries no forward-compatibility risk to retract. Nothing is being built on
top of a new common field that later evidence could contradict, because no
new common field is added. LS-07 remains explicitly open, and phase,
checkpoint, and evidence-schedule concepts remain lifecycle-owned by default,
exactly as they were before this gate. If L02's boundary campaign, an LS-07
phase-evidence study, or the Stage C dam-world studies (PRD LS-09) later
produce evidence that contradicts a decision above — for example, if worlds
genuinely cannot emit task-owned action evidence without a shared reference
envelope — this gate is revisited and the promotion rule reapplied to that
new evidence, not overridden speculatively now.

## What worlds integration receives

Stage C (bounded worlds, PRD LS-09) builds on the following documented
minimal substrate, unchanged by this gate:

**Authored common contracts** (`src/aec_bench/contracts/learning_study.py`,
`learning_study_evidence.py`, `learning_study_assessment.py`,
`learning_family.py`): `LearningStudySpec` / `LearningStudyProtocolSpec` /
compiled plan and steps (`RunExperienceStep`, `ReleaseFeedbackStep`,
`ConsolidateStep`), `LearningArmSpec` and `StudyArmRole`,
`ExperienceRelationSpec` and `ExperienceRelationPurpose`
(`transfer`/`boundary`/`composition`), `LearnerStateRef`,
`FeedbackReleaseRecord`, `LearnerTransitionReceipt`, the runtime-local
`ProjectionResult` and `OutcomeProjection` callback type, and the assessment
validity classes (`LearningComparisonValidity`, `PairedMeasurementValue`,
`ExcludedPair`, `LearningMeasurementResult`, `LearningStudyAssessment`).

**The proven adapter pattern**, demonstrated identically by the artifact
adapter (Gate A) and the lifecycle adapter (L01 review §4, §6):

- task-ID resolution is owner-local (the world owner resolves its own target
  identity; the common layer never parses it);
- the execution condition is fixed per binding and encoded in `adapter_id`,
  proven sufficient for matched-probe validity across every L01 arm;
- reset / structured-memory (or an equivalent owner-defined) treatment pair,
  with copy-on-write state handles;
- a `memory/` + `feedback/`-shaped learner-state tree, validated for size,
  type, and unsafe paths;
- read-only context projection into experience execution, proven immutable by
  byte-compare before/after every execution;
- a strict feedback allowlist plus explicit ineligibility discipline (never
  defaulting a missing or malformed value to `0.0` or success) — demonstrated
  by `drainage_learning.py`'s projector and gate readers;
- probe isolation as a first-class, evidenced fact
  (`arm_isolated`, `lineage_complete`, `probe_feedback_hidden`,
  `probe_state_discarded`, `hidden_evaluation_leaked`), derived from real
  persisted records rather than declared.

**Explicit non-inheritances.** The dam-seepage world adapter does not inherit,
and should not introduce without new evidence: lifecycle mode/visibility
concepts (`fresh_context`/`artifact_memory`/persistent-session semantics),
checkpoint semantics, or any phase model (LS-07's `LifecycleLearningEvidence`
stays lifecycle-owned and is not a template for world evidence). Worlds bring
their own execution condition (bounded observation, authoritative state
transitions, typed world actions) and their own evidence semantics
(task-owned action evidence per PRD LS-09's "Task-owned action evidence"),
exactly as lifecycles brought their own checkpoint and session semantics
without asking the common layer to understand them.

## Acceptance criteria mapping (PRD LS-08)

1. **Lifecycle-only semantics remain lifecycle-owned.** Satisfied: Question 1
   and Question 3 keep phase/checkpoint concepts and all continuity
   mechanisms adapter-owned; the L01 review's field-by-field table is cited
   directly as evidence.
2. **A common hierarchical reference is added only if supported by real
   consumers.** Satisfied by non-action: Question 1 finds neither promotion
   condition met and adds nothing.
3. **Redundant continuity fields are removed.** Satisfied: no redundant
   fields were found. Gate A already removed the provisional continuity
   fields it found redundant; L01 introduced no new common continuity field
   to review, and the common-substrate decision (L01 review §5) confirms zero
   changes to remove from.
4. **The artifact and lifecycle suites rerun after migration.** Satisfied
   trivially: this gate makes no migration (no field moves, is added, or is
   deleted in the common substrate), so no suite requires rerunning as a
   consequence of this decision. The existing suites were already exercised
   by the L01 review itself (L01 review §3, §10).
5. **World integration receives a documented minimal substrate rather than a
   collection of lifecycle assumptions.** Satisfied by the "What worlds
   integration receives" section above, which separates the common contracts
   and proven adapter pattern from lifecycle-specific concepts the dam world
   must not inherit.

## Consequences and open questions

- LS-07 (lifecycle phase evidence, feedback, and scaffolding studies) and the
  L02 boundary campaign remain open and unblocked by this gate; they may
  proceed using the unchanged substrate documented in the L01 review §9.
- Stage C (PRD LS-09, dam-seepage world) may begin integration design against
  the substrate as documented in Gate A and this record. No new common
  contract, enum, or field is pre-authorised for that work; PRD LS-10 (Gate
  C) remains the next required extraction gate after bounded-world evidence
  exists.
- If the dam world's task-owned action evidence turns out to need a shared
  reference envelope in practice, that finding reopens Question 1 with real
  evidence rather than speculation, per the promotion rule.
